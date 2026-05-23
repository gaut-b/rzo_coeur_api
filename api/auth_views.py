"""
api/auth_views.py — Custom password-reset views.

Extends Django's built-in password-reset views to:
  1. Inject a ``callback_url`` into the reset-email context so the link in
     the email carries a ``?callbackUrl=`` parameter that the confirm view
     uses to redirect users to their correct interface after a successful
     password change.
  2. Mark the user's email address as verified in allauth's EmailAddress
     table whenever a password-set/reset token is successfully consumed
     (this covers both the welcome-email flow and the classic
     "Mot de passe oublié" flow).
  3. Block client and recipient users from using this admin reset flow —
     they reset via the auth_kit API, which generates a standard Django
     web-form link via ``mobile_password_reset_url_generator``.
"""

import logging
from urllib.parse import urlencode

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress, get_emailconfirmation_model
from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.utils.encoding import force_bytes
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_encode
from django.views import View

from .models import CustomUser

logger = logging.getLogger(__name__)

# Roles that belong to mobile-app users (CLIENT, RECIPIENT).
# These users reset their password through the app flow, not the admin web form.
_MOBILE_USER_ROLES = {"CLIENT", "RECIPIENT"}

# Session key used to pass the 'mobile reset' flag from the confirm view to
# the complete view across Django's internal post-save redirect.
_SESSION_MOBILE_RESET_KEY = "_password_reset_is_mobile"


class AdminPasswordResetForm(PasswordResetForm):
    """
    Custom reset form that silently skips client and recipient accounts.

    Overrides ``get_users`` to exclude users whose role is ``client`` or
    ``recipient``.  From the browser's perspective the form still submits
    successfully (no enumeration — the done page is always shown).
    """

    def get_users(self, email: str):
        """
        Yield only the users eligible for admin password reset.

        Excludes mobile users (CLIENT, RECIPIENT) — they reset via the app API.
        """
        for user in super().get_users(email):
            if user.role not in _MOBILE_USER_ROLES:
                yield user


class CustomPasswordResetView(auth_views.PasswordResetView):
    """
    Password-reset request view.

    Reads an optional ``callbackUrl`` query param from the request,
    validates it against the same allow-list used by the confirm view
    (same-host URLs and the configured deep-link), and forwards it to
    the reset-email template as a pre-encoded query string.  Unrecognised
    or cross-origin values are silently discarded so that a malicious URL
    never appears in the outgoing email.
    """

    form_class = AdminPasswordResetForm

    def form_valid(self, form):
        """Validate and inject callback_url_query into the email context."""
        raw = self.request.GET.get("callbackUrl", "")
        # Validate before forwarding: reject anything that would not be an
        # accepted redirect target on the confirm view.  This prevents an
        # open-redirect URL from appearing in the password-reset email even
        # in encoded form.
        safe_callback = raw if (raw and _is_allowed_callback_url(raw, self.request)) else ""
        self.extra_email_context = {
            **(self.extra_email_context or {}),
            # Pre-encode as a ready-to-append query string so the template
            # never concatenates raw user input into a URL or href attribute.
            # E.g. ``callbackUrl=%2Fsocial-admin%2Flogin%2F``.
            "callback_url_query": urlencode({"callbackUrl": safe_callback}) if safe_callback else "",
        }
        return super().form_valid(form)


def _is_allowed_callback_url(url: str, request: HttpRequest) -> bool:
    """
    Return True if *url* is safe to redirect to after password reset.

    Accepts same-host relative/absolute URLs only (Django's standard
    open-redirect check using ``url_has_allowed_host_and_scheme``).
    Used by admin flows that pass ``?callbackUrl=`` to redirect back
    to the correct back-office login page after a successful reset.
    """
    return url_has_allowed_host_and_scheme(
        url=url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )


class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    """
    Password-set/reset confirmation view.

    After a successful password change:
    1. Marks the user's email as verified in allauth's EmailAddress table.
    2. Redirects to ``callbackUrl`` (from POST, then GET) if it passes the
       safety check; otherwise falls back to the default success URL.
    """

    def dispatch(self, *args, **kwargs):
        """
        Preserve the ``callbackUrl`` query param through Django's internal
        token-to-set-password redirect.

        Django's parent ``dispatch`` validates the token and then redirects
        from ``/{uid}/{token}/`` to ``/{uid}/set-password/``.  The query
        string is not carried over, so we append it manually.
        """
        response = super().dispatch(*args, **kwargs)
        # Only patch GET responses: the sole purpose here is to carry the
        # callbackUrl through Django's internal token-to-set-password redirect.
        # POST responses are handled by form_valid / get_success_url; patching
        # them here would double-append the param.
        if self.request.method == "GET" and isinstance(response, HttpResponseRedirect):
            callback_url = self.request.GET.get("callbackUrl", "")
            if callback_url:
                location = response["Location"]
                # Only append if not already present (avoid double-appending).
                if "callbackUrl" not in location:
                    response["Location"] = f"{location}?{urlencode({'callbackUrl': callback_url})}"
        return response

    def form_valid(self, form):
        """
        Save the new password, mark the email verified, and redirect.

        Delegates password saving to the parent view, then ensures the
        user's email is marked as verified in allauth's EmailAddress table.
        This covers both the mobile API reset flow (web form) and the admin
        "Mot de passe oublié" flow.
        """
        user: CustomUser = form.user

        # Store a hint for CustomPasswordResetCompleteView so the success
        # page shows the right UI: deep-link button for mobile users (CLIENT)
        # or back-office login links for admin users.
        self.request.session[_SESSION_MOBILE_RESET_KEY] = user.role in _MOBILE_USER_ROLES

        # Delegate to parent (saves password, optionally logs the user in).
        response = super().form_valid(form)
        try:
            EmailAddress.objects.update_or_create(
                user=user,
                email=user.email,
                defaults={"verified": True, "primary": True},
            )
        except Exception:
            logger.exception("Failed to mark email as verified for user pk=%s", user.pk)
        return response

    def get_success_url(self) -> str:
        """
        Return the URL to redirect to after a successful password change.

        Priority:
        1. ``callbackUrl`` from POST data (carried as a hidden form
           field by the confirm template).
        2. ``callbackUrl`` from GET params (fallback, e.g. direct link).
        3. Parent's ``success_url`` (configured in urls.py).
        """
        callback_url = self.request.POST.get("callbackUrl") or self.request.GET.get("callbackUrl", "")

        if callback_url and _is_allowed_callback_url(callback_url, self.request):
            return callback_url

        return super().get_success_url()


# ---------------------------------------------------------------------------
# Mobile / Universal Links support
# ---------------------------------------------------------------------------


class MobileAccountAdapter(DefaultAccountAdapter):
    """
    Custom allauth account adapter.

    Overrides ``get_email_confirmation_url`` so that the link inside the
    signup confirmation email points to the Universal Link path
    ``/app/verify-email/?key=<key>``.  iOS and Android intercept this URL
    and open the app directly.  When the app is not installed the browser
    lands on ``AppVerifyEmailFallbackView``, which shows a branded web page.
    """

    def get_email_confirmation_url(self, request, emailconfirmation) -> str:
        """Return a Universal Link URL for email verification."""
        confirm_path = "/app/verify-email/?" + urlencode({"key": emailconfirmation.key})
        if request is not None:
            return request.build_absolute_uri(confirm_path)
        # request may be None when signals trigger confirmation outside a
        # request cycle (e.g. management commands).  Return the relative path
        # since building an absolute URI requires either a request or the
        # django.contrib.sites framework, which is not always enabled.
        return confirm_path


def mobile_password_reset_url_generator(
    request: HttpRequest,
    user: CustomUser,
    temp_key: str,  # noqa: ARG001 — unused; we generate a Django token instead
) -> str:
    """
    Generate a Django web-form URL for the password reset email (mobile clients).

    auth_kit calls this function (configured via
    ``AUTH_KIT["PASSWORD_RESET_URL_GENERATOR"]``) to build the link included
    in the password reset email sent to ``Client`` users.

    The URL points to Django's standard password-reset confirm view
    (``/auth/reset/<uidb64>/<token>/``), so the user fills in their new
    password in a browser rather than inside the mobile app.  After a
    successful reset the confirmation page shows a deep-link button back
    to the app login screen.

    We discard *temp_key* (allauth's own token format) and generate a
    fresh Django token so that the link works with the existing
    ``CustomPasswordResetConfirmView``.

    Parameters
    ----------
    request:
        The current HTTP request.
    user:
        The user requesting a password reset.
    temp_key:
        Allauth's reset token — intentionally unused here.
    """
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_path = f"/auth/reset/{uidb64}/{token}/"
    return request.build_absolute_uri(reset_path)


class CustomPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    """
    Password-reset success view.

    Extends Django's ``PasswordResetCompleteView`` to inject
    ``mobile_login_url`` (built from ``settings.MOBILE_APP_SCHEME``) into
    the template context, so the deep-link button is never hardcoded.
    """

    def get_context_data(self, **kwargs) -> dict:
        """Add ``mobile_login_url`` and ``is_mobile_reset`` to the template context."""
        context = super().get_context_data(**kwargs)
        context["mobile_login_url"] = f"{settings.MOBILE_APP_SCHEME}://sign-in"
        # Pop the flag set by CustomPasswordResetConfirmView.form_valid.
        # Default False (show admin links) for direct URL access.
        context["is_mobile_reset"] = self.request.session.pop(_SESSION_MOBILE_RESET_KEY, False)
        return context


class AppResetPasswordFallbackView(View):
    """
    Fallback page for old password-reset Universal Links.

    Old emails (sent before the mobile reset flow was simplified) pointed
    to ``/app/reset-password/?uid=…&token=…`` using allauth tokens.  Those
    tokens are incompatible with the current Django web-form confirm view,
    so this page informs the user that the link has expired and directs
    them to request a new reset.
    """

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Render the expired-link page."""
        return render(
            request,
            "emails/app_fallback.html",
            {"action": "reset_password"},
        )


class AppVerifyEmailFallbackView(View):
    """
    Web landing page for email verification Universal Links.

    When iOS/Android opens ``/app/verify-email/?key=<key>`` and the app is NOT
    installed, this view:

    1. Confirms the email server-side immediately (allauth ``confirm()``).
    2. Renders a branded page and tries to open the app login screen via the
       custom-scheme deep link (``rzo-coeur-mobile-app://sign-in``).
    3. If the app is not installed, the browser stays on this page which tells
       the user their email is confirmed and invites them to download the app.

    When the app IS installed, iOS/Android intercepts the Universal Link before
    it reaches this view and opens the app directly.  The app is then
    responsible for calling ``POST /api/auth/registration/verify-email/``
    with the key.
    """

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Confirm the email server-side, then render the fallback page."""
        key = request.GET.get("key", "")
        app_scheme = getattr(settings, "MOBILE_APP_SCHEME", "rzo")

        verified = False
        if key:
            try:
                model = get_emailconfirmation_model()
                confirmation = model.from_key(key)
                if confirmation is not None:
                    confirmation.confirm(request)
                    verified = True
            except Exception:
                # Expired, already-used, or malformed key — verified stays False.
                pass

        # Deep link to the app login screen (email is already confirmed here).
        deep_link = f"{app_scheme}://sign-in"
        return render(
            request,
            "emails/app_fallback.html",
            {"action": "verify_email", "deep_link": deep_link, "verified": verified},
        )


class AppleAppSiteAssociationView(View):
    """
    Serve the Apple App Site Association (AASA) file for Universal Links.

    iOS fetches ``/.well-known/apple-app-site-association`` (without redirect,
    Content-Type: application/json) to verify that this domain is associated
    with the app whose Team ID + Bundle ID is declared in ``IOS_APP_ID``.

    Paths covered (app intercepts these URLs on iOS devices):

    * ``/app/reset-password/`` — client forgot-password link
    * ``/app/verify-email/`` — client signup confirmation link
    * ``/auth/reset/`` — recipient / admin welcome-email activation link
    """

    def get(self, request: HttpRequest, *args, **kwargs) -> JsonResponse:
        """Return the AASA JSON payload."""
        ios_app_id = getattr(settings, "IOS_APP_ID", "TEAMID.fr.reseauxducoeur.app")
        data = {
            "applinks": {
                "details": [
                    {
                        "appIDs": [ios_app_id],
                        "components": [
                            # /app/reset-password/* kept for backward compatibility
                            # with old emails; new emails go directly to /auth/reset/
                            # which is handled by the browser (web form).
                            {"/": "/app/reset-password/*"},
                            {"/": "/app/verify-email/*"},
                        ],
                    }
                ]
            }
        }
        # content_type must be application/json — no text/plain, no redirect.
        return JsonResponse(data)


class AndroidAssetLinksView(View):
    """
    Serve the Android Digital Asset Links file for App Links.

    Android fetches ``/.well-known/assetlinks.json`` to verify that this domain
    is associated with the app whose package name and signing certificate
    fingerprint are declared in ``ANDROID_APP_PACKAGE`` and
    ``ANDROID_SHA256_FINGERPRINT``.
    """

    def get(self, request: HttpRequest, *args, **kwargs) -> JsonResponse:
        """Return the Asset Links JSON payload."""
        android_package = getattr(settings, "ANDROID_APP_PACKAGE", "fr.reseauxducoeur.app")
        android_fp = getattr(settings, "ANDROID_SHA256_FINGERPRINT", "")
        data = [
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {
                    "namespace": "android_app",
                    "package_name": android_package,
                    "sha256_cert_fingerprints": [android_fp] if android_fp else [],
                },
            }
        ]
        return JsonResponse(data, safe=False)

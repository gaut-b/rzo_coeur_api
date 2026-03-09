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
     they have their own dedicated API flow.
"""

import logging
from html import escape as html_escape
from urllib.parse import urlencode

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordResetForm
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme

from .models import CustomUser

logger = logging.getLogger(__name__)

# Roles that may NOT use the admin password-reset flow.
# Clients and recipients have their own API-based flow.
_BLOCKED_ROLES = {"CLIENT", "RECIPIENT"}


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

        Excludes clients and recipients — they reset via the mobile API.
        """
        for user in super().get_users(email):
            if user.role not in _BLOCKED_ROLES:
                yield user


class CustomPasswordResetView(auth_views.PasswordResetView):
    """
    Password-reset request view.

    Reads an optional ``callbackUrl`` query param from the request and
    forwards it to the reset-email template as ``callback_url``, so the
    link in the email carries a ``?callbackUrl=…`` suffix.
    """

    form_class = AdminPasswordResetForm

    def form_valid(self, form):
        """Inject callback_url into the email context before sending."""
        callback_url = self.request.GET.get("callbackUrl", "")
        self.extra_email_context = {
            **(self.extra_email_context or {}),
            "callback_url": callback_url,
        }
        return super().form_valid(form)


def _is_allowed_callback_url(url: str, request: HttpRequest) -> bool:
    """
    Return True if *url* is safe to redirect to after password reset.

    Accepts:
    - Same-host relative/absolute URLs (Django's standard open-redirect
      check using ``url_has_allowed_host_and_scheme``).
    - The configured ``MOBILE_APP_CALLBACK_URL`` deep-link (custom scheme,
      e.g. ``rzo://activate``), which is whitelisted explicitly because
      ``url_has_allowed_host_and_scheme`` rejects non-HTTP schemes.
    """
    mobile_callback = getattr(settings, "MOBILE_APP_CALLBACK_URL", "")
    if mobile_callback and url == mobile_callback:
        return True
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
        if isinstance(response, HttpResponseRedirect):
            callback_url = self.request.GET.get("callbackUrl", "")
            if callback_url:
                location = response["Location"]
                # Only append if not already present (avoid double-appending).
                if "callbackUrl" not in location:
                    response["Location"] = f"{location}?{urlencode({'callbackUrl': callback_url})}"
        return response

    def form_valid(self, form):
        """
        Save the new password and redirect.

        For mobile deep-link callbacks (e.g. ``rzo://activate``), Django's
        ``HttpResponseRedirect`` rejects non-HTTP schemes with
        ``DisallowedRedirect``.  We handle those cases manually: save the
        password, clear the internal session token, mark the email verified,
        then return a minimal HTML page that uses ``<meta http-equiv=refresh>``
        and ``window.location`` to trigger the deep link on the device.

        For ordinary HTTP(S) / relative-path callbacks we delegate to the
        parent (which saves the password and optionally logs the user in),
        then mark the email verified.
        """
        user: CustomUser = form.user
        callback_url = self.request.POST.get("callbackUrl") or self.request.GET.get("callbackUrl", "")
        mobile_url = getattr(settings, "MOBILE_APP_CALLBACK_URL", "")

        if mobile_url and callback_url == mobile_url:
            # Deep-link path: HttpResponseRedirect would raise DisallowedRedirect
            # for non-HTTP schemes, so we manage the save and response ourselves.
            form.save()
            self.request.session.pop(auth_views.INTERNAL_RESET_SESSION_TOKEN, None)
            try:
                EmailAddress.objects.update_or_create(
                    user=user,
                    email=user.email,
                    defaults={"verified": True, "primary": True},
                )
            except Exception:
                logger.exception("Failed to mark email as verified for user pk=%s", user.pk)
            safe_url = html_escape(callback_url)
            return HttpResponse(
                f'<!doctype html><html lang="fr"><head><meta charset="utf-8">'
                f'<meta http-equiv="refresh" content="0;url={safe_url}">'
                f"</head><body>"
                f'<script>window.location.href = "{safe_url}";</script>'
                f"<p>Redirection en cours\u2026</p>"
                f"</body></html>"
            )

        # Standard HTTP / relative-path redirect: delegate to parent.
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

"""
Tests for api/auth_views.py — custom password-reset views.

Coverage targets
----------------
- ``_is_allowed_callback_url``: same-host paths, cross-host URLs, configured
  deep-link, unknown custom scheme, empty string.
- ``AdminPasswordResetForm.get_users``: CLIENT and RECIPIENT roles are silently
  blocked; CASHIER and SOCIAL_WORKER roles are allowed through.
- ``CustomPasswordResetView.form_valid``: ``callbackUrl`` query param is
  forwarded into the password-reset email; blocked roles receive no email.
- ``CustomPasswordResetConfirmView.dispatch``: ``callbackUrl`` is preserved in
  the Location header when Django's internal token-validation redirect fires.
- ``CustomPasswordResetConfirmView.form_valid`` — deep-link path: returns an
  HTML page with ``<meta http-equiv="refresh">``; allauth EmailAddress is
  marked as verified.
- ``CustomPasswordResetConfirmView.form_valid`` — standard path: redirects to
  a safe ``callbackUrl``; falls back to the default success URL for cross-host
  or missing callbacks; allauth EmailAddress is marked as verified.
"""

from allauth.account.models import EmailAddress
from django.contrib.auth.tokens import default_token_generator
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from api.auth_views import AdminPasswordResetForm, _is_allowed_callback_url
from api.models import (
    Cashier,
    Client,
    CustomUser,
    Recipient,
    Shop,
    SocialCenter,
    SocialWorker,
)

# A password that satisfies all default Django validators.
_NEW_PASS = "Tr0ub4dor&3-unique"


# ---------------------------------------------------------------------------
# _is_allowed_callback_url
# ---------------------------------------------------------------------------


class IsAllowedCallbackUrlTests(SimpleTestCase):
    """Unit tests for the ``_is_allowed_callback_url`` helper."""

    def setUp(self) -> None:
        # RequestFactory defaults to SERVER_NAME="testserver", which is what
        # the test client also uses.
        self.request = RequestFactory().get("/")

    def test_relative_path_is_allowed(self) -> None:
        """A relative path (no host) is safe for same-origin use."""
        self.assertTrue(_is_allowed_callback_url("/social-admin/login/", self.request))

    def test_same_host_absolute_url_is_allowed(self) -> None:
        """An absolute URL whose host matches the server is allowed."""
        self.assertTrue(_is_allowed_callback_url("http://testserver/social-admin/login/", self.request))

    def test_cross_host_url_is_rejected(self) -> None:
        """An absolute URL pointing at a different host must be blocked."""
        self.assertFalse(_is_allowed_callback_url("http://evil.com/steal", self.request))

    @override_settings(MOBILE_APP_CALLBACK_URL="rzo://activate")
    def test_configured_deep_link_is_allowed(self) -> None:
        """The exact deep-link value from settings passes the whitelist check."""
        self.assertTrue(_is_allowed_callback_url("rzo://activate", self.request))

    @override_settings(MOBILE_APP_CALLBACK_URL="rzo://activate")
    def test_different_custom_scheme_is_rejected(self) -> None:
        """A custom-scheme URL that does not match the whitelisted value is blocked."""
        self.assertFalse(_is_allowed_callback_url("evil://hack", self.request))

    def test_empty_string_is_rejected(self) -> None:
        """An empty string is not a valid redirect target."""
        self.assertFalse(_is_allowed_callback_url("", self.request))

    @override_settings(MOBILE_APP_CALLBACK_URL="")
    def test_deep_link_rejected_when_mobile_url_not_configured(self) -> None:
        """When MOBILE_APP_CALLBACK_URL is blank, custom schemes are not whitelisted."""
        self.assertFalse(_is_allowed_callback_url("rzo://activate", self.request))


# ---------------------------------------------------------------------------
# AdminPasswordResetForm.get_users — role filtering
# ---------------------------------------------------------------------------


class AdminPasswordResetFormGetUsersTests(TestCase):
    """Verify that CLIENT and RECIPIENT users are filtered out of the form."""

    def _make_user(self, email: str) -> CustomUser:
        """Create an active user with a usable password."""
        return CustomUser.objects.create_user(
            email=email,
            password="testpass123",
            first_name="Test",
            last_name="User",
        )

    def test_client_role_is_excluded(self) -> None:
        """EmailPasswordResetForm must silently skip CLIENT users."""
        user = self._make_user("client@test.com")
        Client.objects.create(user=user)

        result = list(AdminPasswordResetForm().get_users("client@test.com"))

        self.assertEqual(result, [])

    def test_recipient_role_is_excluded(self) -> None:
        """EmailPasswordResetForm must silently skip RECIPIENT users."""
        sc = SocialCenter.objects.create(name="SC", mail="sc@test.com")
        user = self._make_user("recipient@test.com")
        Recipient.objects.create(user=user, social_center=sc)

        result = list(AdminPasswordResetForm().get_users("recipient@test.com"))

        self.assertEqual(result, [])

    def test_cashier_role_is_allowed(self) -> None:
        """CASHIER users may receive a password-reset email."""
        sc = SocialCenter.objects.create(name="SC", mail="sc@test.com")
        shop = Shop.objects.create(name="Shop", social_center=sc)
        user = self._make_user("cashier@test.com")
        Cashier.objects.create(user=user, shop=shop, is_shop_manager=False)

        result = list(AdminPasswordResetForm().get_users("cashier@test.com"))

        self.assertEqual([u.pk for u in result], [user.pk])

    def test_social_worker_role_is_allowed(self) -> None:
        """SOCIAL_WORKER users may receive a password-reset email."""
        sc = SocialCenter.objects.create(name="SC", mail="sc@test.com")
        user = self._make_user("sw@test.com")
        SocialWorker.objects.create(user=user, social_center=sc, is_social_admin=False)

        result = list(AdminPasswordResetForm().get_users("sw@test.com"))

        self.assertEqual([u.pk for u in result], [user.pk])


# ---------------------------------------------------------------------------
# CustomPasswordResetView — callbackUrl forwarding / role gate
# ---------------------------------------------------------------------------


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CustomPasswordResetViewTests(TestCase):
    """Tests for the password-reset *request* view."""

    def setUp(self) -> None:
        sc = SocialCenter.objects.create(name="SC", mail="sc@test.com")
        shop = Shop.objects.create(name="Shop", social_center=sc)
        user = CustomUser.objects.create_user(
            email="cashier@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Cashier",
        )
        Cashier.objects.create(user=user, shop=shop, is_shop_manager=False)
        self.cashier_user = user

    def test_callback_url_included_in_reset_email(self) -> None:
        """
        The callbackUrl query param must appear in the body of the outgoing
        email.  It is pre-encoded in the view, so the email contains the
        percent-encoded form (slashes → ``%2F``) rather than the raw path.
        """
        from django.core import mail

        self.client.post(
            "/auth/password_reset/?callbackUrl=/shop-admin/login/",
            {"email": "cashier@test.com"},
        )

        self.assertEqual(len(mail.outbox), 1)
        # The view calls urlencode({'callbackUrl': '/shop-admin/login/'}), so
        # the query string is ``callbackUrl=%2Fshop-admin%2Flogin%2F``.
        self.assertIn("callbackUrl=%2Fshop-admin%2Flogin%2F", mail.outbox[0].body)

    def test_client_role_receives_no_email(self) -> None:
        """CLIENT users must be silently skipped — no email sent."""
        from django.core import mail

        client_user = CustomUser.objects.create_user(
            email="client2@test.com",
            password="testpass123",
            first_name="Client",
            last_name="User",
        )
        Client.objects.create(user=client_user)

        self.client.post(
            "/auth/password_reset/",
            {"email": "client2@test.com"},
        )

        self.assertEqual(len(mail.outbox), 0)

    def test_recipient_role_receives_no_email(self) -> None:
        """RECIPIENT users must be silently skipped — no email sent."""
        from django.core import mail

        sc = SocialCenter.objects.create(name="SC2", mail="sc2@test.com")
        recip_user = CustomUser.objects.create_user(
            email="recipient2@test.com",
            password="testpass123",
            first_name="Recip",
            last_name="User",
        )
        Recipient.objects.create(user=recip_user, social_center=sc)

        self.client.post(
            "/auth/password_reset/",
            {"email": "recipient2@test.com"},
        )

        self.assertEqual(len(mail.outbox), 0)

    def test_disallowed_callback_url_is_omitted_from_email(self) -> None:
        """
        A callbackUrl that points at a foreign host must be silently dropped
        before the email is sent — it must not appear in the email body even
        in encoded form.
        """
        from django.core import mail

        self.client.post(
            "/auth/password_reset/?callbackUrl=http://evil.com/steal",
            {"email": "cashier@test.com"},
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("evil.com", mail.outbox[0].body)
        self.assertNotIn("callbackUrl", mail.outbox[0].body)

    @override_settings(MOBILE_APP_CALLBACK_URL="rzo://activate")
    def test_whitelisted_deep_link_is_forwarded_in_email(self) -> None:
        """
        The configured deep-link value must pass validation and appear
        (percent-encoded) in the reset email.
        """
        from django.core import mail

        self.client.post(
            "/auth/password_reset/?callbackUrl=rzo://activate",
            {"email": "cashier@test.com"},
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("callbackUrl=rzo%3A%2F%2Factivate", mail.outbox[0].body)


# ---------------------------------------------------------------------------
# CustomPasswordResetConfirmView helpers
# ---------------------------------------------------------------------------


def _make_confirm_user(email: str = "user@test.com") -> CustomUser:
    """Create an active user for password-reset confirm tests."""
    return CustomUser.objects.create_user(
        email=email,
        password="OldPass99!",
        first_name="Test",
        last_name="User",
    )


def _uid_token(user: CustomUser) -> tuple[str, str]:
    """Return (uidb64, token) for the given user."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return uid, token


# ---------------------------------------------------------------------------
# CustomPasswordResetConfirmView.dispatch — callbackUrl preservation
# ---------------------------------------------------------------------------


@override_settings(MOBILE_APP_CALLBACK_URL="rzo://activate")
class CustomPasswordResetConfirmViewDispatchTests(TestCase):
    """Verify that callbackUrl survives Django's internal token-redirect."""

    def setUp(self) -> None:
        self.user = _make_confirm_user()
        self.uid, self.token = _uid_token(self.user)

    def test_callback_url_appended_to_redirect_location(self) -> None:
        """
        When the GET includes callbackUrl, it must appear (URL-encoded) in the
        Location header of the 302 that Django emits after token validation.
        """
        url = f"/auth/reset/{self.uid}/{self.token}/?callbackUrl=/social-admin/login/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        # urlencode encodes the slashes, so check for the encoded form.
        self.assertIn("callbackUrl=", response["Location"])
        self.assertIn("social-admin", response["Location"])

    def test_no_callback_url_location_is_unchanged(self) -> None:
        """Without callbackUrl in the request, the redirect Location is unmodified."""
        url = f"/auth/reset/{self.uid}/{self.token}/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("callbackUrl", response["Location"])


# ---------------------------------------------------------------------------
# CustomPasswordResetConfirmView.form_valid — deep-link path
# ---------------------------------------------------------------------------


@override_settings(
    MOBILE_APP_CALLBACK_URL="rzo://activate",
    AUTH_PASSWORD_VALIDATORS=[],
)
class CustomPasswordResetConfirmViewDeepLinkTests(TestCase):
    """
    Tests for the deep-link (non-HTTP scheme) branch of form_valid.

    When callbackUrl equals MOBILE_APP_CALLBACK_URL, Django's
    HttpResponseRedirect cannot be used (it rejects non-HTTP schemes), so the
    view returns a plain HTML page with a meta-refresh instead.
    """

    def setUp(self) -> None:
        self.user = _make_confirm_user("deeplink@test.com")
        self.uid, self.token = _uid_token(self.user)
        # Trigger Django's internal token-to-session redirect so that a
        # subsequent POST to the set-password URL has a valid session.
        response = self.client.get(f"/auth/reset/{self.uid}/{self.token}/")
        self.assertEqual(response.status_code, 302)
        self.set_password_url = f"/auth/reset/{self.uid}/set-password/"

    def test_returns_html_response_with_meta_refresh(self) -> None:
        """The deep-link path must return 200 HTML (not a redirect)."""
        response = self.client.post(
            f"{self.set_password_url}?callbackUrl=rzo://activate",
            {"new_password1": _NEW_PASS, "new_password2": _NEW_PASS},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'meta http-equiv="refresh"', response.content)
        self.assertIn(b"rzo://activate", response.content)

    @override_settings(MOBILE_APP_CALLBACK_URL="rzo://activate&source=email")
    def test_deep_link_url_is_html_escaped_in_response(self) -> None:
        """
        The deep-link URL is passed through html.escape before being embedded
        in the HTML response.  A URL containing ``&`` must appear as ``&amp;``
        so that the meta-refresh attribute and the JS assignment are safe.
        """
        # Re-trigger the token-validation GET with the new deep-link value so
        # the session is fresh for this whitelisted URL.
        user = _make_confirm_user("deeplink_esc@test.com")
        uid, token = _uid_token(user)
        self.client.get(f"/auth/reset/{uid}/{token}/")
        set_password_url = f"/auth/reset/{uid}/set-password/"

        response = self.client.post(
            f"{set_password_url}?callbackUrl=rzo://activate%26source%3Demail",
            {"new_password1": _NEW_PASS, "new_password2": _NEW_PASS},
        )

        self.assertEqual(response.status_code, 200)
        # The raw ``&`` must be escaped as ``&amp;`` in the HTML.
        self.assertIn(b"&amp;", response.content)
        self.assertNotIn(b"rzo://activate&source", response.content)

    def test_deep_link_marks_email_address_as_verified(self) -> None:
        """After the deep-link flow, allauth EmailAddress must be verified."""
        self.client.post(
            f"{self.set_password_url}?callbackUrl=rzo://activate",
            {"new_password1": _NEW_PASS, "new_password2": _NEW_PASS},
        )

        self.assertTrue(EmailAddress.objects.filter(user=self.user, verified=True).exists())


# ---------------------------------------------------------------------------
# CustomPasswordResetConfirmView.form_valid — standard HTTP/relative path
# ---------------------------------------------------------------------------


@override_settings(
    MOBILE_APP_CALLBACK_URL="rzo://activate",
    AUTH_PASSWORD_VALIDATORS=[],
)
class CustomPasswordResetConfirmViewStandardPathTests(TestCase):
    """
    Tests for the standard (HTTP/relative) branch of form_valid.

    For ordinary callbacks the view delegates to Django's parent and then
    marks the email address as verified.
    """

    def _setup_session(self, email: str) -> tuple[CustomUser, str]:
        """
        Create a fresh user, complete the token-validation GET, and return
        (user, set_password_url) ready for a POST in the same session.
        """
        user = _make_confirm_user(email)
        uid, token = _uid_token(user)
        response = self.client.get(f"/auth/reset/{uid}/{token}/")
        self.assertEqual(response.status_code, 302)
        return user, f"/auth/reset/{uid}/set-password/"

    def test_valid_relative_callback_url_is_used_as_redirect(self) -> None:
        """A safe relative callbackUrl must be the redirect target."""
        _user, set_password_url = self._setup_session("sw@test.com")

        response = self.client.post(
            set_password_url,
            {
                "new_password1": _NEW_PASS,
                "new_password2": _NEW_PASS,
                "callbackUrl": "/social-admin/login/",
            },
        )

        self.assertRedirects(
            response,
            "/social-admin/login/",
            fetch_redirect_response=False,
        )

    def test_cross_host_callback_falls_back_to_default_success_url(self) -> None:
        """A callbackUrl pointing at a different host must be ignored."""
        _user, set_password_url = self._setup_session("sw2@test.com")

        response = self.client.post(
            set_password_url,
            {
                "new_password1": _NEW_PASS,
                "new_password2": _NEW_PASS,
                "callbackUrl": "http://evil.com/steal",
            },
        )

        self.assertRedirects(
            response,
            "/auth/reset/done/",
            fetch_redirect_response=False,
        )

    def test_missing_callback_url_falls_back_to_default_success_url(self) -> None:
        """When callbackUrl is absent the view uses the configured success_url."""
        _user, set_password_url = self._setup_session("sw3@test.com")

        response = self.client.post(
            set_password_url,
            {"new_password1": _NEW_PASS, "new_password2": _NEW_PASS},
        )

        self.assertRedirects(
            response,
            "/auth/reset/done/",
            fetch_redirect_response=False,
        )

    def test_standard_path_marks_email_address_as_verified(self) -> None:
        """After a successful standard-path reset, allauth EmailAddress is verified."""
        user, set_password_url = self._setup_session("sw4@test.com")

        self.client.post(
            set_password_url,
            {
                "new_password1": _NEW_PASS,
                "new_password2": _NEW_PASS,
                "callbackUrl": "/social-admin/login/",
            },
        )

        self.assertTrue(EmailAddress.objects.filter(user=user, verified=True).exists())

    def test_callback_url_carried_via_get_param_on_post(self) -> None:
        """
        callbackUrl may arrive via the GET query string on the POST request
        (e.g. when the reset link carried it and the template did not inject
        a hidden field).  The view must honour the GET param as a fallback
        *without* dispatch appending it a second time to the redirect.
        """
        _user, set_password_url = self._setup_session("sw5@test.com")

        response = self.client.post(
            f"{set_password_url}?callbackUrl=/shop-admin/login/",
            {"new_password1": _NEW_PASS, "new_password2": _NEW_PASS},
        )

        # Must redirect cleanly to the callback — no extra ?callbackUrl= appended.
        self.assertRedirects(
            response,
            "/shop-admin/login/",
            fetch_redirect_response=False,
        )


# ---------------------------------------------------------------------------
# MobileAccountAdapter.get_email_confirmation_url
# ---------------------------------------------------------------------------


class MobileAccountAdapterTests(SimpleTestCase):
    """Unit tests for the custom allauth account adapter."""

    def _make_email_confirmation(self, key: str):
        """Return a minimal stub with a ``key`` attribute."""

        class _Stub:
            pass

        stub = _Stub()
        stub.key = key
        return stub

    def test_confirmation_url_points_to_app_verify_path(self) -> None:
        """get_email_confirmation_url must return a URL rooted at /app/verify-email/."""
        from api.auth_views import MobileAccountAdapter

        adapter = MobileAccountAdapter()
        request = RequestFactory().get("/")
        ec = self._make_email_confirmation("testkey123")

        url = adapter.get_email_confirmation_url(request, ec)

        self.assertIn("/app/verify-email/", url)
        self.assertIn("key=testkey123", url)

    def test_confirmation_url_key_is_url_encoded(self) -> None:
        """Special characters in the key must be percent-encoded."""
        from api.auth_views import MobileAccountAdapter

        adapter = MobileAccountAdapter()
        request = RequestFactory().get("/")
        ec = self._make_email_confirmation("key with spaces+special")

        url = adapter.get_email_confirmation_url(request, ec)

        self.assertNotIn(" ", url)
        self.assertIn("/app/verify-email/", url)

    def test_confirmation_url_without_request_still_returns_string(self) -> None:
        """When request is None the method returns a relative path (no sites framework needed)."""
        from api.auth_views import MobileAccountAdapter

        adapter = MobileAccountAdapter()
        ec = self._make_email_confirmation("nokey")

        url = adapter.get_email_confirmation_url(None, ec)

        self.assertIsInstance(url, str)
        self.assertIn("/app/verify-email/", url)
        self.assertIn("key=nokey", url)


# ---------------------------------------------------------------------------
# mobile_password_reset_url_generator
# ---------------------------------------------------------------------------


class MobilePasswordResetUrlGeneratorTests(TestCase):
    """Unit tests for the auth_kit PASSWORD_RESET_URL_GENERATOR callable."""

    def setUp(self) -> None:
        self.user = CustomUser.objects.create_user(
            email="mobile_reset@test.com",
            password="pass",
            first_name="Mobile",
            last_name="User",
        )

    def test_url_points_to_app_reset_path(self) -> None:
        """The generated URL must be rooted at /app/reset-password/."""
        from api.auth_views import mobile_password_reset_url_generator

        request = RequestFactory().get("/")
        url = mobile_password_reset_url_generator(request, self.user, "tok123")

        self.assertIn("/app/reset-password/", url)

    def test_url_contains_uid_and_token(self) -> None:
        """uid and token query params must both appear in the URL."""
        from api.auth_views import mobile_password_reset_url_generator

        request = RequestFactory().get("/")
        url = mobile_password_reset_url_generator(request, self.user, "sometoken")

        self.assertIn("uid=", url)
        self.assertIn("token=sometoken", url)

    def test_uid_is_base36_encoded(self) -> None:
        """uid must be the allauth base36-encoded primary key (not raw UUID/int)."""
        from allauth.account.utils import user_pk_to_url_str

        from api.auth_views import mobile_password_reset_url_generator

        request = RequestFactory().get("/")
        url = mobile_password_reset_url_generator(request, self.user, "tok")
        expected_uid = user_pk_to_url_str(self.user)

        self.assertIn(f"uid={expected_uid}", url)


# ---------------------------------------------------------------------------
# AppResetPasswordFallbackView  (/app/reset-password/)
# ---------------------------------------------------------------------------


@override_settings(MOBILE_APP_SCHEME="rzo")
class AppResetPasswordFallbackViewTests(SimpleTestCase):
    """Tests for the /app/reset-password/ fallback web page."""

    def test_get_returns_200(self) -> None:
        """GET /app/reset-password/ must return HTTP 200."""
        response = self.client.get("/app/reset-password/")
        self.assertEqual(response.status_code, 200)

    def test_response_contains_deep_link_with_uid_and_token(self) -> None:
        """The rendered page must embed a deep link containing uid and token."""
        response = self.client.get(
            "/app/reset-password/",
            {"uid": "abc123", "token": "tok456"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "uid=abc123")
        self.assertContains(response, "token=tok456")

    def test_response_uses_mobile_app_scheme(self) -> None:
        """The deep link must use the MOBILE_APP_SCHEME defined in settings."""
        response = self.client.get("/app/reset-password/", {"uid": "x", "token": "y"})

        self.assertContains(response, "rzo://reset-password")

    def test_missing_params_do_not_crash(self) -> None:
        """GET without uid/token query params must not raise — empty strings used."""
        response = self.client.get("/app/reset-password/")
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# AppVerifyEmailFallbackView  (/app/verify-email/)
# ---------------------------------------------------------------------------


@override_settings(MOBILE_APP_SCHEME="rzo")
class AppVerifyEmailFallbackViewTests(TestCase):
    """Tests for the /app/verify-email/ fallback web page."""

    def test_get_returns_200(self) -> None:
        """GET /app/verify-email/ must return HTTP 200 even without a valid key."""
        response = self.client.get("/app/verify-email/")
        self.assertEqual(response.status_code, 200)

    def test_invalid_key_shows_error_state(self) -> None:
        """An invalid/expired key must render without crashing (verified=False)."""
        response = self.client.get("/app/verify-email/", {"key": "invalidkey"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Adresse email confirmée")

    def test_missing_key_param_does_not_crash(self) -> None:
        """GET without key param must not raise — treated as invalid key."""
        response = self.client.get("/app/verify-email/")
        self.assertEqual(response.status_code, 200)

    def test_response_contains_login_deep_link_when_verified(self) -> None:
        """The confirmed page must embed the rzo://login deep link when email is verified."""
        from allauth.account.models import EmailAddress, get_emailconfirmation_model

        # Create a real user + email confirmation entry so verification succeeds.
        user = CustomUser.objects.create_user(
            email="verify_test@test.com",
            password="pass",
            first_name="Test",
            last_name="User",
        )
        email_address = EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=False)
        model = get_emailconfirmation_model()
        confirmation = model.create(email_address)

        response = self.client.get("/app/verify-email/", {"key": confirmation.key})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "rzo://login")
        self.assertContains(response, "Adresse email confirm\u00e9e")


# ---------------------------------------------------------------------------
# AppleAppSiteAssociationView  (/.well-known/apple-app-site-association)
# ---------------------------------------------------------------------------


@override_settings(IOS_APP_ID="TEAM01.fr.reseauxducoeur.app")
class AppleAppSiteAssociationViewTests(SimpleTestCase):
    """Tests for the iOS Universal Links AASA endpoint."""

    def test_returns_200(self) -> None:
        """GET /.well-known/apple-app-site-association must return HTTP 200."""
        response = self.client.get("/.well-known/apple-app-site-association")
        self.assertEqual(response.status_code, 200)

    def test_content_type_is_json(self) -> None:
        """Response Content-Type must be application/json (iOS requirement)."""
        response = self.client.get("/.well-known/apple-app-site-association")
        self.assertIn("application/json", response["Content-Type"])

    def test_payload_contains_app_id_from_settings(self) -> None:
        """The JSON payload must include the IOS_APP_ID from settings."""
        import json

        response = self.client.get("/.well-known/apple-app-site-association")
        data = json.loads(response.content)

        app_ids = data["applinks"]["details"][0]["appIDs"]
        self.assertIn("TEAM01.fr.reseauxducoeur.app", app_ids)

    def test_payload_covers_all_required_paths(self) -> None:
        """
        The AASA must declare components for /app/reset-password/,
        /app/verify-email/ and /auth/reset/ (recipient welcome emails).
        """
        import json

        response = self.client.get("/.well-known/apple-app-site-association")
        data = json.loads(response.content)

        components = data["applinks"]["details"][0]["components"]
        declared_paths = [c["/"] for c in components if "/" in c]

        self.assertTrue(
            any("/app/reset-password/" in p for p in declared_paths),
            "Missing /app/reset-password/* in AASA components",
        )
        self.assertTrue(
            any("/app/verify-email/" in p for p in declared_paths),
            "Missing /app/verify-email/* in AASA components",
        )
        self.assertTrue(
            any("/auth/reset/" in p for p in declared_paths),
            "Missing /auth/reset/* in AASA components",
        )


# ---------------------------------------------------------------------------
# AndroidAssetLinksView  (/.well-known/assetlinks.json)
# ---------------------------------------------------------------------------


@override_settings(
    ANDROID_APP_PACKAGE="fr.reseauxducoeur.app",
    ANDROID_SHA256_FINGERPRINT="AA:BB:CC:DD",
)
class AndroidAssetLinksViewTests(SimpleTestCase):
    """Tests for the Android App Links Digital Asset Links endpoint."""

    def test_returns_200(self) -> None:
        """GET /.well-known/assetlinks.json must return HTTP 200."""
        response = self.client.get("/.well-known/assetlinks.json")
        self.assertEqual(response.status_code, 200)

    def test_content_type_is_json(self) -> None:
        """Response Content-Type must be application/json (Android requirement)."""
        response = self.client.get("/.well-known/assetlinks.json")
        self.assertIn("application/json", response["Content-Type"])

    def test_payload_is_a_list(self) -> None:
        """The JSON payload must be a top-level array."""
        import json

        response = self.client.get("/.well-known/assetlinks.json")
        data = json.loads(response.content)
        self.assertIsInstance(data, list)

    def test_payload_contains_package_name_from_settings(self) -> None:
        """The JSON payload must include ANDROID_APP_PACKAGE from settings."""
        import json

        response = self.client.get("/.well-known/assetlinks.json")
        data = json.loads(response.content)

        self.assertEqual(data[0]["target"]["package_name"], "fr.reseauxducoeur.app")

    def test_payload_contains_fingerprint_from_settings(self) -> None:
        """The JSON payload must include ANDROID_SHA256_FINGERPRINT from settings."""
        import json

        response = self.client.get("/.well-known/assetlinks.json")
        data = json.loads(response.content)

        self.assertIn("AA:BB:CC:DD", data[0]["target"]["sha256_cert_fingerprints"])

    @override_settings(ANDROID_SHA256_FINGERPRINT="")
    def test_empty_fingerprint_yields_empty_list(self) -> None:
        """When ANDROID_SHA256_FINGERPRINT is empty, the fingerprints list must be []."""
        import json

        response = self.client.get("/.well-known/assetlinks.json")
        data = json.loads(response.content)

        self.assertEqual(data[0]["target"]["sha256_cert_fingerprints"], [])

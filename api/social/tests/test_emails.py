"""
Tests for api/emails.py — send_account_welcome_email.

Coverage targets
----------------
- Reset URL structure: the path contains uidb64 (derived from user.pk) and
  a valid token for the user.
- callbackUrl encoding — relative path: slashes are percent-encoded so the
  query parameter is unambiguous.
- callbackUrl encoding — deep link: a custom-scheme URL (``rzo://activate``)
  is encoded correctly and included in the reset URL.
- The email is addressed to the user's email address.
- The email subject matches the expected French localisation string.
- Email-send failure is swallowed: no exception propagates to the caller.
"""

import re
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from api.emails import send_account_welcome_email
from api.models import CustomUser

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_user(email: str = "worker@test.com") -> CustomUser:
    """Return an unsaved-then-saved CustomUser with a usable password."""
    return CustomUser.objects.create_user(
        email=email,
        password="SomePass99!",
        first_name="Test",
        last_name="User",
    )


def _expected_uid(user: CustomUser) -> str:
    """Reproduce the uidb64 the function will derive from the user's pk."""
    return urlsafe_base64_encode(force_bytes(user.pk))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SendAccountWelcomeEmailTests(TestCase):
    """Unit tests for ``send_account_welcome_email``."""

    def setUp(self) -> None:
        self.user = _make_user()
        # RequestFactory builds a minimal fake request; SERVER_NAME defaults
        # to "testserver" so build_absolute_uri returns http://testserver/...
        self.request = RequestFactory().get("/")

    # ------------------------------------------------------------------
    # Reset URL structure
    # ------------------------------------------------------------------

    def test_reset_url_contains_correct_uidb64(self) -> None:
        """The reset link must embed the base64-encoded pk of the user."""
        send_account_welcome_email(self.user, "/social-admin/login/", self.request)

        uid = _expected_uid(self.user)
        body = mail.outbox[0].body
        self.assertIn(f"/auth/reset/{uid}/", body)

    def test_reset_url_contains_valid_token(self) -> None:
        """The token in the reset URL must be verifiable by the token generator."""
        send_account_welcome_email(self.user, "/social-admin/login/", self.request)

        body = mail.outbox[0].body
        uid = _expected_uid(self.user)
        # Extract the token from the URL pattern /auth/reset/<uid>/<token>/
        pattern = rf"/auth/reset/{re.escape(uid)}/([^/?]+)/"
        match = re.search(pattern, body)
        self.assertIsNotNone(match, "Token not found in reset URL")
        token = match.group(1)
        self.assertTrue(
            default_token_generator.check_token(self.user, token),
            f"Token '{token}' is not valid for user pk={self.user.pk}",
        )

    def test_reset_url_is_absolute(self) -> None:
        """build_absolute_uri must produce a fully-qualified URL in the email."""
        send_account_welcome_email(self.user, "/social-admin/login/", self.request)

        body = mail.outbox[0].body
        self.assertIn("http://testserver/auth/reset/", body)

    # ------------------------------------------------------------------
    # callbackUrl encoding — relative path
    # ------------------------------------------------------------------

    def test_relative_callback_url_is_encoded_in_reset_link(self) -> None:
        """
        A relative path like ``/social-admin/login/`` must appear
        percent-encoded as the ``callbackUrl`` query parameter so that the
        slashes are unambiguous inside the query string.
        """
        send_account_welcome_email(self.user, "/social-admin/login/", self.request)

        body = mail.outbox[0].body
        # urlencode encodes / as %2F
        self.assertIn("callbackUrl=%2Fsocial-admin%2Flogin%2F", body)

    def test_shop_admin_callback_url_is_encoded_in_reset_link(self) -> None:
        """Same encoding check for the shop-admin login path."""
        send_account_welcome_email(self.user, "/shop-admin/login/", self.request)

        body = mail.outbox[0].body
        self.assertIn("callbackUrl=%2Fshop-admin%2Flogin%2F", body)

    # ------------------------------------------------------------------
    # callbackUrl encoding — deep link
    # ------------------------------------------------------------------

    def test_deep_link_callback_url_is_encoded_in_reset_link(self) -> None:
        """
        A deep-link value like ``rzo://activate`` must also be percent-encoded
        into the ``callbackUrl`` query parameter (``://`` → ``%3A%2F%2F``).
        """
        send_account_welcome_email(self.user, "rzo://activate", self.request)

        body = mail.outbox[0].body
        self.assertIn("callbackUrl=rzo%3A%2F%2Factivate", body)

    # ------------------------------------------------------------------
    # Recipient and subject
    # ------------------------------------------------------------------

    def test_email_is_sent_to_user_email_address(self) -> None:
        """The To header must be the user's email, not some default address."""
        send_account_welcome_email(self.user, "/social-admin/login/", self.request)

        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_email_subject_is_correct(self) -> None:
        """The subject must match the expected French welcome string."""
        send_account_welcome_email(self.user, "/social-admin/login/", self.request)

        self.assertEqual(
            mail.outbox[0].subject,
            "Bienvenue sur Les Réseaux du Coeur — Activez votre compte",
        )

    def test_exactly_one_email_is_sent(self) -> None:
        """Each call must produce exactly one outgoing message."""
        send_account_welcome_email(self.user, "/social-admin/login/", self.request)

        self.assertEqual(len(mail.outbox), 1)

    # ------------------------------------------------------------------
    # Resilience — email-send failure must not propagate
    # ------------------------------------------------------------------

    def test_send_failure_is_swallowed(self) -> None:
        """
        If the SMTP backend raises, the exception must be caught so that
        account creation is not interrupted.
        """
        with (
            patch(
                "django.core.mail.EmailMessage.send",
                side_effect=OSError("SMTP down"),
            ),
            self.assertLogs("api.emails", level="ERROR"),
        ):
            # Must not raise.
            send_account_welcome_email(self.user, "/social-admin/login/", self.request)

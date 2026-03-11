"""
Page Object: PasswordResetPage  (/auth/password_reset/)

Covers the shared password-reset flow accessible from any custom admin login:
  - Submitting the reset-request form.
  - Asserting the "email sent" confirmation page.
  - Querying the Mailhog HTTP API to verify email delivery.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

import requests
from playwright.sync_api import Page, expect


class PasswordResetPage:
    """Encapsulates interactions with the shared password-reset flow."""

    RESET_FORM_URL_PATTERN = re.compile(r"/auth/password_reset/$")
    DONE_URL_PATTERN = re.compile(r"/auth/password_reset/done/")

    def __init__(self, base_url: str, mailhog_api_url: str) -> None:
        """
        Parameters
        ----------
        base_url:
            Root URL of the Django server (e.g. ``http://127.0.0.1:8001``).
        mailhog_api_url:
            Base URL of the Mailhog HTTP API
            (e.g. ``http://localhost:8025``).
        """
        self.base_url = base_url
        self.reset_url = f"{base_url}/auth/password_reset/"
        self.mailhog_api_url = mailhog_api_url

    # ── Browser interactions ──────────────────────────────────────────────────

    def goto(self, page: Page) -> None:
        """Navigate directly to the password-reset request form."""
        page.goto(self.reset_url)
        expect(page).to_have_url(self.RESET_FORM_URL_PATTERN)

    def submit_reset_request(self, page: Page, email: str) -> None:
        """
        Fill the email field and submit the reset-request form.

        After submission Django always redirects to the 'done' confirmation
        page whether or not the address is registered — by design, to prevent
        user enumeration.
        """
        page.goto(self.reset_url)
        page.locator("#id_email").fill(email)
        page.locator('[type="submit"]').click()

    def expect_email_sent_confirmation(self, page: Page) -> None:
        """Assert that the browser landed on the 'email sent' confirmation page."""
        expect(page).to_have_url(self.DONE_URL_PATTERN)

    # ── Mailhog helpers ───────────────────────────────────────────────────────

    def clear_mailhog(self) -> None:
        """
        Delete all messages stored in Mailhog.

        Raises ``requests.HTTPError`` if the API returns a non-2xx status so
        that a misconfigured URL or an unready Mailhog instance surfaces as a
        hard failure rather than leaving stale messages that silently corrupt
        subsequent assertions.
        """
        response = requests.delete(f"{self.mailhog_api_url}/api/v1/messages", timeout=5)
        response.raise_for_status()

    def get_messages_for(self, recipient_email: str) -> list[dict]:
        """
        Return all Mailhog messages addressed to *recipient_email*.

        Mailhog exposes each message's raw recipients in ``msg["Raw"]["To"]``
        as a flat list of strings (e.g. ``["user@test.local"]``), which is
        the most reliable field to filter on.

        Parameters
        ----------
        recipient_email:
            The email address to filter on (case-insensitive).

        Returns
        -------
        list[dict]:
            List of Mailhog message dicts (may be empty).
        """
        resp = requests.get(
            f"{self.mailhog_api_url}/api/v2/messages",
            params={"limit": 50},
            timeout=5,
        )
        resp.raise_for_status()
        messages = resp.json().get("items", [])
        needle = recipient_email.lower()
        return [msg for msg in messages if any(needle == addr.lower() for addr in msg.get("Raw", {}).get("To", []))]

    def expect_welcome_email_received(self, recipient_email: str) -> None:
        """
        Assert (via Mailhog API) that a welcome / account-creation email was
        delivered to *recipient_email* containing a password-setup link.

        Raises
        ------
        AssertionError:
            If no matching email is found.
        """
        messages = self.get_messages_for(recipient_email)
        assert messages, (
            f"No email found in Mailhog for {recipient_email!r}. "
            "Make sure the welcome email was sent after user creation."
        )
        # The welcome email body must contain the set-password link path.
        body = messages[0].get("Content", {}).get("Body", "")
        assert "/auth/reset/" in body, (
            f"Welcome email for {recipient_email!r} does not contain a "
            f"password-reset link.  Body preview: {body[:200]!r}"
        )

    def expect_reset_email_received(self, recipient_email: str) -> None:
        """
        Assert (via Mailhog API) that a password-reset email was delivered
        to *recipient_email* containing a reset link.

        Raises
        ------
        AssertionError:
            If no matching email is found.
        """
        messages = self.get_messages_for(recipient_email)
        assert messages, f"No password-reset email found in Mailhog for {recipient_email!r}."
        body = messages[0].get("Content", {}).get("Body", "")
        assert "/auth/reset/" in body, (
            f"Reset email for {recipient_email!r} does not contain a password-reset link.  Body preview: {body[:200]!r}"
        )

    def extract_reset_url_from_email(self, recipient_email: str) -> str:
        """
        Return the first ``/auth/reset/…`` URL (with optional callbackUrl
        query string) found in the HTML body of the most recent Mailhog
        message addressed to *recipient_email*.

        Raises
        ------
        AssertionError:
            If no email is found or no reset URL can be extracted.
        """
        messages = self.get_messages_for(recipient_email)
        assert messages, f"No email found in Mailhog for {recipient_email!r} — cannot extract reset URL."
        # Mailhog stores the HTML part in MIME parts; fall back to Body.
        # Use ``or {}`` because Mailhog may store the key with a null value
        # (e.g. for HTML-only, non-multipart emails) rather than omitting it,
        # and ``.get(key, default)`` only substitutes when the key is absent.
        body = ""
        for part in (messages[0].get("MIME") or {}).get("Parts", []):
            content_types = part.get("Headers", {}).get("Content-Type", [""])
            if any("text/html" in ct.lower() for ct in content_types):
                body = part.get("Body", "")
                break
        if not body:
            body = messages[0].get("Content", {}).get("Body", "")

        # Match the full href containing /auth/reset/ (URL may be wrapped in
        # href="…" or appear as plain text).
        match = re.search(r'href="([^"]*?/auth/reset/[^"]*?)"', body)
        if not match:
            # Fallback: plain-text URL (no surrounding quotes)
            match = re.search(r"(https?://\S+/auth/reset/\S+)", body)
        assert match, f"No /auth/reset/ URL found in email for {recipient_email!r}. Body preview: {body[:300]!r}"
        # Rewrite the origin (scheme + host + port) to match the test server,
        # since Django builds the URL using the Docker-internal host.
        extracted = match.group(1)
        parsed = urlparse(extracted)
        base = urlparse(self.base_url)
        return urlunparse(parsed._replace(scheme=base.scheme, netloc=base.netloc))

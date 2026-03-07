"""
Page Object: SocialAdminPage  (/social-admin/)

Covers:
  - Navigating to the Recipient and SocialWorker creation forms.
  - Filling and submitting those forms.
"""

from __future__ import annotations

import re
import uuid

from playwright.sync_api import Page, expect


class SocialAdminPage:
    """Page object for the /social-admin/ Django admin site."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.index_url = f"{base_url}/social-admin/"

    def goto_index(self, page: Page) -> None:
        """Navigate to the social-admin index."""
        page.goto(self.index_url)
        expect(page).to_have_url(re.compile(r"/social-admin/(?!.*login)"))

    def goto_add_recipient(self, page: Page) -> None:
        """Navigate directly to the Add Recipient form."""
        page.goto(f"{self.base_url}/social-admin/api/recipient/add/")

    def goto_add_social_worker(self, page: Page) -> None:
        """Navigate directly to the Add SocialWorker form."""
        page.goto(f"{self.base_url}/social-admin/api/socialworker/add/")

    def create_recipient(
        self,
        page: Page,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> str:
        """
        Fill and submit the Recipient creation form.

        Returns the email address used so callers can assert on it.
        """
        suffix = uuid.uuid4().hex[:8]
        email = f"e2e-new-recipient-{suffix}@test.local"
        first_name = first_name or "New"
        last_name = last_name or f"Recipient{suffix}"

        self.goto_add_recipient(page)

        page.locator("#id_email").fill(email)
        page.locator("#id_first_name").fill(first_name)
        page.locator("#id_last_name").fill(last_name)
        page.locator("#id_password").fill("TestPass123!")

        page.locator('[name="_save"]').click()

        # After a successful save Django redirects to the list view.
        expect(page).to_have_url(re.compile(r"/social-admin/api/recipient/"))
        return email

    def create_social_worker(
        self,
        page: Page,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> str:
        """
        Fill and submit the SocialWorker creation form.

        Returns the email address used.
        """
        suffix = uuid.uuid4().hex[:8]
        email = f"e2e-new-sw-{suffix}@test.local"
        first_name = first_name or "New"
        last_name = last_name or f"Worker{suffix}"

        self.goto_add_social_worker(page)

        page.locator("#id_email").fill(email)
        page.locator("#id_first_name").fill(first_name)
        page.locator("#id_last_name").fill(last_name)
        page.locator("#id_password").fill("TestPass123!")

        page.locator('[name="_save"]').click()

        expect(page).to_have_url(re.compile(r"/social-admin/api/socialworker/"))
        return email

    def expect_has_access(self, page: Page) -> None:
        """Assert that the current page is the admin index (not login)."""
        expect(page).to_have_url(re.compile(r"/social-admin/(?!.*login)"))

    def expect_no_access(self, page: Page) -> None:
        """Assert that the user was redirected back to the login page."""
        expect(page.locator(".errornote")).to_be_visible()

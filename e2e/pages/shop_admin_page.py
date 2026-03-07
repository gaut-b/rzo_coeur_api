"""
Page Object: ShopAdminPage  (/shop-admin/)

Covers:
  - Viewing the article list.
  - Creating a cashier (shop-manager only).
  - Asserting that the Cashier module is/is not visible in the nav.
"""

from __future__ import annotations

import re
import uuid

from playwright.sync_api import Page, expect


class ShopAdminPage:
    """Page object for the /shop-admin/ Django admin site."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.index_url = f"{base_url}/shop-admin/"
        self.articles_url = f"{base_url}/shop-admin/api/article/"
        self.add_cashier_url = f"{base_url}/shop-admin/api/cashier/add/"

    def goto_index(self, page: Page) -> None:
        """Navigate to the shop-admin index."""
        page.goto(self.index_url)
        expect(page).to_have_url(re.compile(r"/shop-admin/(?!.*login)"))

    def goto_articles(self, page: Page) -> None:
        """Navigate to the Article list in shop-admin."""
        page.goto(self.articles_url)
        expect(page).to_have_url(re.compile(r"/shop-admin/api/article/"))

    def expect_articles_visible(self, page: Page) -> None:
        """Assert that at least one article row is shown."""
        expect(page.locator("#result_list tbody tr").first).to_be_visible(timeout=10_000)

    def expect_cashier_module_visible(self, page: Page) -> None:
        """Assert that the Cashier module appears in the admin nav sidebar."""
        expect(page.get_by_role("link", name="Cashiers")).to_be_visible()

    def expect_cashier_module_hidden(self, page: Page) -> None:
        """Assert that the Cashier module does NOT appear for regular cashiers."""
        expect(page.get_by_role("link", name="Cashiers")).to_have_count(0)

    def create_cashier(
        self,
        page: Page,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        role: str = "False",
    ) -> str:
        """
        Fill and submit the Cashier creation form.

        Parameters
        ----------
        role:
            ``"True"`` for shop manager, ``"False"`` for regular cashier.

        Returns the email address used.
        """
        suffix = uuid.uuid4().hex[:8]
        email = f"e2e-new-cashier-{suffix}@test.local"
        first_name = first_name or "New"
        last_name = last_name or f"Cashier{suffix}"

        page.goto(self.add_cashier_url)

        page.locator("#id_email").fill(email)
        page.locator("#id_first_name").fill(first_name)
        page.locator("#id_last_name").fill(last_name)
        page.locator("#id_password").fill("TestPass123!")
        page.locator("#id_role").select_option(value=role)

        page.locator('[name="_save"]').click()

        # Successful save redirects to the cashier list.
        expect(page).to_have_url(re.compile(r"/shop-admin/api/cashier/"))
        return email

    def expect_has_access(self, page: Page) -> None:
        """Assert that the user has a valid session on shop-admin."""
        expect(page).to_have_url(re.compile(r"/shop-admin/(?!.*login)"))

    def expect_no_access(self, page: Page) -> None:
        """Assert that access was denied (error message visible on login page)."""
        expect(page.locator(".errornote")).to_be_visible()

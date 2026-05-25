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
        self.export_csv_url = f"{base_url}/shop-admin/api/article/export-csv/"

    def goto_index(self, page: Page) -> None:
        """Navigate to the shop-admin index."""
        page.goto(self.index_url)
        expect(page).to_have_url(re.compile(r"/shop-admin/(?!.*login)"))

    def goto_articles(self, page: Page) -> None:
        """Navigate to the Article list in shop-admin."""
        page.goto(self.articles_url)
        expect(page).to_have_url(re.compile(r"/shop-admin/api/article/"))

    def goto_add_cashier(self, page: Page) -> None:
        """Navigate directly to the Add Cashier form."""
        page.goto(self.add_cashier_url)
        expect(page).to_have_url(re.compile(r"/shop-admin/api/cashier/add/"))

    def expect_articles_visible(self, page: Page) -> None:
        """Assert that at least one article row is shown."""
        expect(page.locator("#result_list tbody tr").first).to_be_visible(timeout=10_000)

    def expect_cashier_module_visible(self, page: Page) -> None:
        """Assert that the Cashier module appears in the admin nav sidebar."""
        expect(page.get_by_role("link", name="Vendeurs")).to_be_visible()

    def expect_cashier_module_hidden(self, page: Page) -> None:
        """Assert that the Cashier module does NOT appear for regular cashiers."""
        expect(page.get_by_role("link", name="Vendeurs")).to_have_count(0)

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

    # -----------------------------------------------------------------------
    # CSV export helpers
    # -----------------------------------------------------------------------

    def goto_export_csv(self, page: Page) -> None:
        """Navigate directly to the CSV export form."""
        page.goto(self.export_csv_url)
        expect(page).to_have_url(re.compile(r"/shop-admin/api/article/export-csv/"))

    def expect_export_button_visible(self, page: Page) -> None:
        """Assert that the 'Exporter en CSV' button is shown on the article list."""
        expect(page.get_by_role("link", name="Exporter en CSV")).to_be_visible()

    def expect_export_button_hidden(self, page: Page) -> None:
        """Assert that the 'Exporter en CSV' button is NOT shown."""
        expect(page.get_by_role("link", name="Exporter en CSV")).to_have_count(0)

    def download_csv_export(
        self,
        page: Page,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> str:
        """
        Fill the export form with the given dates and return the CSV content.

        Parameters
        ----------
        date_from:
            ISO date string (``YYYY-MM-DD``) for the lower bound, or None to
            leave the field at its default value.
        date_to:
            ISO date string for the upper bound, or None to leave at default.

        Returns the decoded text content of the downloaded CSV file.
        """
        self.goto_export_csv(page)

        if date_from is not None:
            page.locator("#id_date_from").fill(date_from)
        if date_to is not None:
            page.locator("#id_date_to").fill(date_to)

        with page.expect_download() as dl_info:
            page.locator('[type="submit"]').click()

        download = dl_info.value
        assert re.match(
            r"export_resos_coeur-\d{4}-\d{2}-\d{2}\.csv",
            download.suggested_filename,
        ), f"Expected a dated .csv download, got: {download.suggested_filename!r}"
        path = download.path()
        with open(path, encoding="utf-8-sig") as fh:
            return fh.read()

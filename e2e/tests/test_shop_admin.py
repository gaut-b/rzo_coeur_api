"""
test_shop_admin.py

Covers the /shop-admin/ interface:
  - Non-cashier users are denied access
  - A regular cashier can log in and view articles
  - A regular cashier does NOT see the Cashier management module
  - A shop manager can log in and view articles
  - A shop manager can create a new cashier
  - CSV export: button visibility, download, date-range filtering
"""

import csv
import io
from datetime import date

import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import BASE_URL, E2E_PASSWORD
from e2e.pages.admin_login_page import AdminLoginPage
from e2e.pages.shop_admin_page import ShopAdminPage


@pytest.mark.usefixtures("django_server")
class TestShopAdminAccess:
    """Access-control tests for /shop-admin/."""

    def test_non_cashier_is_denied_on_shop_admin(self, anon_page: Page) -> None:
        """
        A social worker (who has no cashier profile) must be denied access
        to /shop-admin/ and see a permission-denied error.
        """
        login_page = AdminLoginPage(BASE_URL, "shop-admin")
        login_page.login(anon_page, "e2e-social-worker@test.local", E2E_PASSWORD)
        login_page.expect_error(anon_page, "Vous n'avez pas la permission")

    def test_cashier_can_login_via_form(self, anon_page: Page) -> None:
        """
        A cashier can authenticate through the /shop-admin/ login form.
        Verifies the form itself works for valid credentials.
        """
        login_page = AdminLoginPage(BASE_URL, "shop-admin")
        login_page.login(anon_page, "e2e-cashier@test.local", E2E_PASSWORD)
        login_page.expect_logged_in(anon_page, "shop-admin")

    def test_cashier_can_access_shop_admin(self, cashier_page: Page) -> None:
        """A regular cashier reaches the /shop-admin/ index."""
        page_obj = ShopAdminPage(BASE_URL)
        page_obj.goto_index(cashier_page)
        page_obj.expect_has_access(cashier_page)

    def test_shop_manager_can_access_shop_admin(self, shop_manager_page: Page) -> None:
        """A shop manager reaches the /shop-admin/ index."""
        page_obj = ShopAdminPage(BASE_URL)
        page_obj.goto_index(shop_manager_page)
        page_obj.expect_has_access(shop_manager_page)


@pytest.mark.usefixtures("django_server")
class TestShopAdminArticles:
    """Article list visibility tests for /shop-admin/."""

    def test_cashier_can_view_articles(self, cashier_page: Page) -> None:
        """A regular cashier can see the article list for their shop."""
        page_obj = ShopAdminPage(BASE_URL)
        page_obj.goto_articles(cashier_page)
        page_obj.expect_articles_visible(cashier_page)

    def test_shop_manager_can_view_articles(self, shop_manager_page: Page) -> None:
        """A shop manager can see the article list for their shop."""
        page_obj = ShopAdminPage(BASE_URL)
        page_obj.goto_articles(shop_manager_page)
        page_obj.expect_articles_visible(shop_manager_page)

    def test_cashier_cannot_see_cashier_module(self, cashier_page: Page) -> None:
        """
        A regular cashier (not a shop manager) must NOT see the Cashiers
        module in the admin navigation sidebar.
        """
        page_obj = ShopAdminPage(BASE_URL)
        page_obj.goto_index(cashier_page)
        page_obj.expect_cashier_module_hidden(cashier_page)

    def test_shop_manager_sees_cashier_module(self, shop_manager_page: Page) -> None:
        """
        A shop manager has is_shop_manager=True and must see the Cashiers
        module in the admin navigation sidebar.
        """
        page_obj = ShopAdminPage(BASE_URL)
        page_obj.goto_index(shop_manager_page)
        page_obj.expect_cashier_module_visible(shop_manager_page)


@pytest.mark.usefixtures("django_server")
class TestShopAdminCashierCreation:
    """Cashier creation tests — only available to shop managers."""

    def test_shop_manager_can_create_cashier(self, shop_manager_page: Page) -> None:
        """A shop manager fills and submits the cashier creation form."""
        page_obj = ShopAdminPage(BASE_URL)
        email = page_obj.create_cashier(shop_manager_page, role="False")
        expect(shop_manager_page.locator("#result_list")).to_contain_text(email)


@pytest.mark.usefixtures("django_server")
class TestShopAdminCsvExport:
    """CSV export tests for /shop-admin/api/article/export-csv/."""

    def test_export_button_visible_for_shop_manager(self, shop_manager_page: Page) -> None:
        """Shop manager sees the 'Exporter en CSV' button on the article list."""
        page_obj = ShopAdminPage(BASE_URL)
        page_obj.goto_articles(shop_manager_page)
        page_obj.expect_export_button_visible(shop_manager_page)

    def test_export_button_hidden_for_cashier(self, cashier_page: Page) -> None:
        """A regular cashier does NOT see the 'Exporter en CSV' button."""
        page_obj = ShopAdminPage(BASE_URL)
        page_obj.goto_articles(cashier_page)
        page_obj.expect_export_button_hidden(cashier_page)

    def test_cashier_export_url_is_redirected(self, cashier_page: Page) -> None:
        """
        Navigating directly to the export URL as a non-manager must redirect
        back to the article changelist (no direct URL bypass).
        """
        page_obj = ShopAdminPage(BASE_URL)
        cashier_page.goto(page_obj.export_csv_url)
        expect(cashier_page).to_have_url(f"{BASE_URL}/shop-admin/api/article/")

    def test_export_form_has_prefilled_dates(self, shop_manager_page: Page) -> None:
        """
        The export form must be pre-filled with the first day of the current
        month as date_from and today as date_to.
        """
        page_obj = ShopAdminPage(BASE_URL)
        page_obj.goto_export_csv(shop_manager_page)
        today = date.today()
        first_of_month = today.replace(day=1).isoformat()
        expect(shop_manager_page.locator("#id_date_from")).to_have_value(first_of_month)
        expect(shop_manager_page.locator("#id_date_to")).to_have_value(today.isoformat())

    def test_export_downloads_csv_file(self, shop_manager_page: Page) -> None:
        """
        Submitting the export form triggers a CSV file download with the
        expected header row and at least one data row for the seeded articles.
        """
        page_obj = ShopAdminPage(BASE_URL)
        # No date filter — export all articles.
        csv_content = page_obj.download_csv_export(shop_manager_page)
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        # At least a header row + the 3 seeded E2E articles.
        assert len(rows) >= 4, f"Expected ≥4 rows, got {len(rows)}"
        header = rows[0]
        assert "ID" in header
        assert "Nom" in header
        assert "Code-barres" in header
        assert "E-mail client" in header

    def test_export_csv_contains_seeded_articles(self, shop_manager_page: Page) -> None:
        """Downloaded CSV must contain the three seeded E2E articles by name."""
        page_obj = ShopAdminPage(BASE_URL)
        csv_content = page_obj.download_csv_export(shop_manager_page)
        assert "E2E Yogurt" in csv_content
        assert "E2E Pasta" in csv_content
        assert "E2E Tomato Sauce" in csv_content

    def test_export_future_date_range_yields_empty_body(self, shop_manager_page: Page) -> None:
        """
        A date range in the future (no articles exist) must still produce a
        valid CSV with only the header row.
        """
        page_obj = ShopAdminPage(BASE_URL)
        csv_content = page_obj.download_csv_export(
            shop_manager_page,
            date_from="2099-01-01",
            date_to="2099-12-31",
        )
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        # Only the header row — no data.
        assert len(rows) == 1, f"Expected 1 row (header only), got {len(rows)}"

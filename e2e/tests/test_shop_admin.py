"""
test_shop_admin.py

Covers the /shop-admin/ interface:
  - Non-cashier users are denied access
  - A regular cashier can log in and view articles
  - A regular cashier does NOT see the Cashier management module
  - A shop manager can log in and view articles
  - A shop manager can create a new cashier
"""

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
        login_page.expect_error(anon_page, "You do not have permission")

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

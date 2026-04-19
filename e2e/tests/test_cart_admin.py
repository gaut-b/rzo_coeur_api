"""
test_cart_admin.py

Covers the /cart-admin/ interface:
  - Social worker can see available articles
  - Social worker can create a cart directly from the article list
  - Social worker can add articles to an existing cart (bulk action)
  - Social worker can delete a cart by unchecking all articles on the edit page
"""

import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import BASE_URL, E2E_PASSWORD
from e2e.pages.admin_login_page import AdminLoginPage
from e2e.pages.admin_page import AdminPage
from e2e.pages.cart_admin_page import CartAdminPage


@pytest.mark.usefixtures("django_server")
class TestCartAdminAccess:
    """Access-control tests for /cart-admin/."""

    def test_social_admin_can_access_cart_admin_site(self, social_admin_page: Page) -> None:
        """A social admin user also has access to /cart-admin/."""
        social_admin_page.goto(f"{BASE_URL}/cart-admin/")
        assert "/cart-admin/" in social_admin_page.url
        assert "/login/" not in social_admin_page.url

    def test_social_worker_can_access_cart_admin_site(self, cart_admin_page: Page) -> None:
        """A social worker can access /cart-admin/ (their primary interface)."""
        cart_admin_page.goto(f"{BASE_URL}/cart-admin/")
        assert "/cart-admin/" in cart_admin_page.url
        assert "/login/" not in cart_admin_page.url

    def test_staff_can_access_cart_admin_site(self, staff_page: Page) -> None:
        """A staff user can access /cart-admin/."""
        staff_page.goto(f"{BASE_URL}/cart-admin/")
        assert "/cart-admin/" in staff_page.url
        assert "/login/" not in staff_page.url

    def test_social_worker_can_login_via_form(self, anon_page: Page) -> None:
        """
        A social worker can authenticate through the /cart-admin/ login form.
        Verifies the form itself works for valid credentials.
        """
        login_page = AdminLoginPage(BASE_URL, "cart-admin")
        login_page.login(anon_page, "e2e-social-worker@test.local", E2E_PASSWORD)
        login_page.expect_logged_in(anon_page, "cart-admin")


@pytest.mark.usefixtures("django_server")
class TestCartAdmin:
    """Tests for the /cart-admin/ site."""

    def test_social_worker_can_see_available_articles(self, cart_admin_page: Page) -> None:
        """
        The Article list shows the 3 articles seeded by seed_e2e_data
        (all available, cart=None).
        """
        page_obj = CartAdminPage(BASE_URL)
        page_obj.goto_articles(cart_admin_page)
        page_obj.expect_articles_visible(cart_admin_page)

    def test_social_worker_can_create_cart_from_article_list(self, cart_admin_page: Page) -> None:
        """
        A social worker selects an available article and creates a new cart
        using the "Créer un panier" bulk action. The page must redirect to
        the cart detail/change view.
        """
        page_obj = CartAdminPage(BASE_URL)
        cart_id = page_obj.create_cart(cart_admin_page, article_indices=[0])
        assert cart_id > 0, "Cart creation did not return a valid id"

    def test_social_worker_can_add_articles_to_cart(self, cart_admin_page: Page) -> None:
        """
        A social worker selects an available article and assigns it to an
        existing cart using the "Ajouter à un panier existant" bulk action.
        """
        page_obj = CartAdminPage(BASE_URL)

        # Create a cart with the first available article.
        cart_id = page_obj.create_cart(cart_admin_page, article_indices=[0])
        assert cart_id > 0

        # Assign the next available article (first of the remaining) to the
        # same cart via the "Ajouter à un panier existant" action.
        page_obj.assign_articles_to_cart(cart_admin_page, cart_id=cart_id, article_indices=[0])

        page_obj.goto_articles(cart_admin_page)
        expect(cart_admin_page.locator("#result_list")).to_be_visible()

    def test_social_worker_can_delete_cart_by_unchecking_all_articles(self, cart_admin_page: Page) -> None:
        """
        A social worker navigates to a cart's edit page, unchecks all articles,
        and saves. A native confirmation dialog appears; upon acceptance the
        cart is deleted and the user is redirected to the cart changelist.
        """
        page_obj = CartAdminPage(BASE_URL)
        # Re-use the first non-collected cart already in the DB (created by
        # earlier tests in this session).
        cart_id = page_obj.get_first_cart_id(cart_admin_page)
        assert cart_id > 0, "No cart found in the DB to run the deletion test"
        page_obj.delete_cart_by_unchecking_all(cart_admin_page, cart_id)

    def test_articles_are_removed_when_cart_is_collected(self, cart_admin_page: Page, staff_page: Page) -> None:
        """
        Assign articles to a cart, attribute cart, when cart is collected, articles should
        not be visibles anymore.
        """
        page_obj = CartAdminPage(BASE_URL)
        page_admin_obj = AdminPage(BASE_URL)
        cart_id = page_obj.create_cart(cart_admin_page, article_indices=[0])
        assert cart_id > 0
        page_obj.assign_articles_to_cart(cart_admin_page, cart_id=cart_id, article_indices=[0, 1])
        page_obj.goto_articles(cart_admin_page)
        page_obj.expect_articles_visible(cart_admin_page)
        page_admin_obj.mark_cart_as_collected(staff_page, cart_id=cart_id)
        page_obj.goto_articles(cart_admin_page)
        page_obj.expect_articles_not_visible(cart_admin_page)

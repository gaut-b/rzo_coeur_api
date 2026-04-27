"""
test_cart_admin.py

Covers the /cart-admin/ interface:
  - Social worker can see available articles
  - Social worker can create a cart and assign it to a recipient
  - Social worker can add articles to a cart (bulk action)
  - Social worker can remove articles from a cart (bulk action)
"""

import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import BASE_URL, E2E_PASSWORD
from e2e.pages.admin_login_page import AdminLoginPage
from e2e.pages.cart_admin_page import CartAdminPage
from e2e.pages.admin_page import AdminPage


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

    def test_social_worker_can_create_cart_and_assign_recipient(self, cart_admin_page: Page) -> None:
        """
        A social worker creates a cart and assigns the E2E recipient to it.
        The page must redirect to the cart detail/change view.
        """
        page_obj = CartAdminPage(BASE_URL)
        # "Test Recipient" matches the __str__ of the Recipient model
        cart_id = page_obj.create_cart(cart_admin_page, recipient_display="Test Recipient")
        assert cart_id > 0, "Cart creation did not return a valid id"

    def test_social_worker_can_add_articles_to_cart(self, cart_admin_page: Page) -> None:
        """
        A social worker selects available articles and assigns them to a cart
        using the bulk action "Assign Article to Cart".
        """
        page_obj = CartAdminPage(BASE_URL)

        # Create a fresh cart to assign articles to
        cart_id = page_obj.create_cart(cart_admin_page, recipient_display="Test Recipient")
        assert cart_id > 0

        # Select the first two articles (indices 0 and 1) and assign them
        page_obj.assign_articles_to_cart(cart_admin_page, cart_id=cart_id, article_indices=[0, 1])

        # Navigate back to the article list and verify the articles appear
        # with a non-"Available" status (the status column text changes after
        # assignment). We just check that the list still loads cleanly.
        page_obj.goto_articles(cart_admin_page)
        expect(cart_admin_page.locator("#result_list")).to_be_visible()

    def test_social_worker_can_remove_articles_from_cart(self, cart_admin_page: Page) -> None:
        """
        After assigning articles, a social worker can remove them from their
        cart using the "remove_from_cart" bulk action.
        """
        page_obj = CartAdminPage(BASE_URL)

        # Assign article at index 2 to a cart first
        cart_id = page_obj.create_cart(cart_admin_page, recipient_display="Test Recipient")
        assert cart_id > 0
        page_obj.assign_articles_to_cart(cart_admin_page, cart_id=cart_id, article_indices=[0])

        # Now navigate back to articles and remove the article we just assigned.
        # Filter the list to show only articles in this cart.
        cart_admin_page.goto(f"{BASE_URL}/cart-admin/api/article/?cart__id__exact={cart_id}")
        expect(cart_admin_page.locator("#result_list tbody tr")).to_have_count(1, timeout=10_000)

        page_obj.remove_articles_from_cart(cart_admin_page, article_indices=[0])

        # After removal the article should no longer appear in the cart filter
        cart_admin_page.goto(f"{BASE_URL}/cart-admin/api/article/?cart__id__exact={cart_id}")
        expect(cart_admin_page.locator("#result_list tbody tr")).to_have_count(0, timeout=10_000)

    def test_articles_are_removed_when_cart_is_collected(self, cart_admin_page: Page, staff_page: Page) -> None:
        """
        Assign articles to a cart, attribute cart, when cart is collected, articles should
        not be visibles anymore.
        """
        page_obj = CartAdminPage(BASE_URL)
        page_admin_obj = AdminPage(BASE_URL)
        cart_id = page_obj.create_cart(cart_admin_page, recipient_display="Test Recipient")
        assert cart_id > 0
        page_obj.assign_articles_to_cart(cart_admin_page, cart_id=cart_id, article_indices=[0, 1, 2])
        page_admin_obj.mark_cart_as_collected(staff_page, cart_id=cart_id)
        page_obj.expect_articles_not_visible(cart_admin_page)

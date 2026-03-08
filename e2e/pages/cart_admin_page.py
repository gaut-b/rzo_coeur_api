"""
Page Object: CartAdminPage  (/cart-admin/)

Covers:
  - Viewing available articles.
  - Creating a cart and assigning it to a recipient.
  - Selecting articles and using the "Assign Article to Cart" action.
  - Removing articles from a cart.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect


class CartAdminPage:
    """Page object for the /cart-admin/ Django admin site."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.index_url = f"{base_url}/cart-admin/"
        self.articles_url = f"{base_url}/cart-admin/api/article/"
        self.carts_url = f"{base_url}/cart-admin/api/cart/"
        self.add_cart_url = f"{base_url}/cart-admin/api/cart/add/"

    def goto_articles(self, page: Page) -> None:
        """Navigate to the Article list in cart-admin."""
        page.goto(self.articles_url)
        expect(page).to_have_url(re.compile(r"/cart-admin/api/article/"))

    def goto_carts(self, page: Page) -> None:
        """Navigate to the Cart list in cart-admin."""
        page.goto(self.carts_url)
        expect(page).to_have_url(re.compile(r"/cart-admin/api/cart/"))

    def expect_articles_visible(self, page: Page) -> None:
        """Assert that at least the seeded articles are shown in the list."""
        # Django admin renders results in a <table id="result_list">
        expect(page.locator("#result_list tbody tr").first).to_be_visible(timeout=10_000)

    def _select_autocomplete(self, page: Page, field_id: str, search_text: str = "") -> None:
        """
        Interact with a Django Select2 autocomplete field.

        Clicks the Select2 trigger for *field_id*, optionally types
        *search_text* to filter results, waits for results to load via AJAX
        and clicks the first selectable option.

        Parameters
        ----------
        field_id:
            The HTML ``id`` attribute of the underlying ``<select>`` element
            (e.g. ``"id_shop"``).  The Select2 trigger is the
            ``select2-selection--single`` span that immediately follows the
            hidden ``<select>`` in the DOM.
        search_text:
            Optional text typed into the search input to narrow results.
        """
        # Use the hidden <select> as an anchor to find its adjacent Select2
        # widget, then click the combobox trigger (role="combobox").
        page.locator(f"#{field_id} + .select2-container .select2-selection--single").click()
        if search_text:
            page.locator(".select2-search__field").fill(search_text)
        # Disabled options are used by Select2 as non-selectable placeholders
        # (e.g. the "Searching…" spinner shown while AJAX loads).  Wait until
        # at least one real, selectable result is visible before clicking.
        first_result = page.locator(".select2-results__option:not(.select2-results__option--disabled)").first
        expect(first_result).to_be_visible(timeout=5_000)
        first_result.click()

    def create_cart(self, page: Page, recipient_display: str) -> int:
        """
        Fill and submit the Cart creation form.

        Parameters
        ----------
        recipient_display:
            The string representation of the recipient as it appears in the
            autocomplete widget (e.g. ``"Test Recipient"``).

        Returns the Django id of the created cart (parsed from the redirect URL).
        """
        page.goto(self.add_cart_url)

        # Select shop — only one shop exists in E2E data; open the autocomplete
        # dropdown and pick the first result without filtering.
        self._select_autocomplete(page, "id_shop")

        # Select recipient by searching their display name.
        self._select_autocomplete(page, "id_recipient", recipient_display)

        page.locator('[name="_continue"]').click()

        # Redirects to /cart-admin/api/cart/<id>/change/
        expect(page).to_have_url(re.compile(r"/cart-admin/api/cart/\d+"))
        # Extract id from URL  e.g. /cart-admin/api/cart/3/change/
        url = page.url
        parts = [p for p in url.split("/") if p.isdigit()]
        return int(parts[-1]) if parts else -1

    def assign_articles_to_cart(self, page: Page, cart_id: int, article_indices: list[int]) -> None:
        """
        Select articles by row index (0-based) and assign them to *cart_id*
        using the "Assign Article to Cart" bulk action.

        Only available articles (cart=None) are shown — the URL is filtered
        to ``?cart__isnull=True`` to ensure repeatable indices across runs.

        Parameters
        ----------
        article_indices:
            Row indices (0-based) of the articles to select.
        """
        # Filter to only available articles so indices are stable between runs.
        page.goto(f"{self.articles_url}?cart__isnull=True")

        # Select checkboxes for the specified rows
        rows = page.locator("#result_list tbody tr")
        for idx in article_indices:
            rows.nth(idx).locator('input[type="checkbox"]').check()

        # Choose the assign action from the <select>
        page.locator('select[name="action"]').select_option(label="Assign Article to Cart")

        # Submit the action form — opens the action form modal/page
        page.locator('[type="submit"][name="index"]').click()

        # Fill the cart id in the action form
        page.locator("#id_cart").select_option(value=str(cart_id))
        page.locator('[type="submit"]').last.click()

        # Should be back on the article list
        expect(page).to_have_url(re.compile(r"/cart-admin/api/article/"))

    def remove_articles_from_cart(self, page: Page, article_indices: list[int]) -> None:
        """
        Select articles by row index (0-based) and remove them from their cart
        using the "remove_from_cart" bulk action.

        Operates on the article list as currently loaded — navigate to the
        desired filter before calling if needed.
        """
        rows = page.locator("#result_list tbody tr")
        for idx in article_indices:
            rows.nth(idx).locator('input[type="checkbox"]').check()

        page.locator('select[name="action"]').select_option(value="remove_from_cart")
        page.locator('[type="submit"][name="index"]').click()

        expect(page).to_have_url(re.compile(r"/cart-admin/api/article/"))

    def expect_has_access(self, page: Page) -> None:
        """Assert that the user has a valid session on cart-admin."""
        expect(page).to_have_url(re.compile(r"/cart-admin/(?!.*login)"))

    def expect_no_access(self, page: Page) -> None:
        """Assert that access was denied (error message or redirect to login)."""
        expect(page.locator(".errornote")).to_be_visible()

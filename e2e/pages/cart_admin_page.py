"""
Page Object: CartAdminPage  (/cart-admin/)

Covers:
  - Viewing available articles.
  - Creating a cart directly from a selection of available articles.
  - Selecting articles and using the "Ajouter à un panier existant" action.
  - Deleting a cart by unchecking all articles on the edit page.
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

    def expect_articles_not_visible(self, page: Page) -> None:
        """Assert that articles are not shown anymore in the list."""
        # Django admin renders results in a <table id="result_list">
        expect(page.locator("#result_list tbody tr").first).not_to_be_visible()

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

    def create_cart(self, page: Page, article_indices: list[int]) -> int:
        """
        Select articles by row index (0-based) from the available article list
        and create a new PENDING cart using the "Créer un panier" bulk action.

        Parameters
        ----------
        article_indices:
            Row indices (0-based) of the available articles to include in
            the new cart.

        Returns the Django id of the created cart (parsed from the redirect URL).
        """
        page.goto(f"{self.articles_url}?cart__isnull=True")
        rows = page.locator("#result_list tbody tr")
        for idx in article_indices:
            rows.nth(idx).locator('input[type="checkbox"]').check()
        page.locator('select[name="action"]').select_option(label="Créer un panier")
        page.locator('[type="submit"][name="index"]').click()
        # Server redirects to /cart-admin/api/cart/<id>/change/
        expect(page).to_have_url(re.compile(r"/cart-admin/api/cart/\d+"))
        url = page.url
        parts = [p for p in url.split("/") if p.isdigit()]
        return int(parts[-1]) if parts else -1

    def assign_articles_to_cart(self, page: Page, cart_id: int, article_indices: list[int]) -> None:
        """
        Select articles by row index (0-based) and assign them to *cart_id*
        using the "Ajouter à un panier existant" bulk action.

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
        page.locator('select[name="action"]').select_option(label="Ajouter à un panier existant")

        # Submit the action form — opens the action form modal/page
        page.locator('[type="submit"][name="index"]').click()

        # Pick the cart via the Select2 autocomplete widget (AutocompleteSelect).
        # Search by cart id so the result is unique regardless of shop name or date.
        self._select_autocomplete(page, "id_cart", search_text=str(cart_id))
        page.locator('[type="submit"]').last.click()

        # Should be back on the article list
        expect(page).to_have_url(re.compile(r"/cart-admin/api/article/"))

    def get_first_cart_id(self, page: Page) -> int:
        """
        Navigate to the cart changelist and return the Django id of the first
        listed cart.
        """
        page.goto(self.carts_url)
        first_link = page.locator("#result_list tbody tr").first.locator("a").first
        expect(first_link).to_be_visible(timeout=10_000)
        href = first_link.get_attribute("href") or ""
        parts = [p for p in href.split("/") if p.isdigit()]
        return int(parts[-1]) if parts else -1

    def delete_cart_by_unchecking_all(self, page: Page, cart_id: int) -> None:
        """
        Navigate to a cart's change page, uncheck all article checkboxes,
        accept the native ``confirm()`` dialog triggered by the JS guard, and
        save. The server deletes the empty cart and redirects to the
        changelist.
        """
        page.goto(f"{self.carts_url}{cart_id}/change/")
        checkboxes = page.locator('input[name="articles"]')
        for i in range(checkboxes.count()):
            checkboxes.nth(i).uncheck()
        # Register the dialog handler BEFORE clicking save so Playwright
        # intercepts the native confirm() dialog and accepts it.
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator('[name="_save"]').click()
        expect(page).to_have_url(re.compile(r"/cart-admin/api/cart/(?!\d)"))

    def expect_has_access(self, page: Page) -> None:
        """Assert that the user has a valid session on cart-admin."""
        expect(page).to_have_url(re.compile(r"/cart-admin/(?!.*login)"))

    def expect_no_access(self, page: Page) -> None:
        """Assert that access was denied (error message or redirect to login)."""
        expect(page.locator(".errornote")).to_be_visible()

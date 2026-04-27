"""
Page Object: AdminPage  (/admin/)

Covers:
  - Navigating to the Cart list.
  - Marking a cart as collected.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect


class AdminPage:
    """Page object for the /admin/ Django admin site."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.index_url = f"{base_url}/admin/"
        self.cart_url = f"{base_url}/admin/api/cart/"

    def goto_cart(self, page: Page) -> None:
        """Navigate to the Cart list in admin."""
        page.goto(self.cart_url)
        expect(page).to_have_url(re.compile(r"/admin/api/cart/"))

    def mark_cart_as_collected(self, page: Page, cart_id: int) -> None:
        page.goto(f"{self.cart_url}{cart_id}/change/")
        page.locator("#id_collected_at_0").fill("2026-04-27")
        page.locator("#id_collected_at_1").fill("13:48:00")
        page.locator('[name="_save"]').click()
        expect(page).to_have_url(re.compile(r"/admin/api/cart/"))

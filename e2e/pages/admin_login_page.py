"""
Page Object: AdminLoginPage

Shared login page helper for all four Django admin sites:
  /admin/, /shop-admin/, /social-admin/, /cart-admin/
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect


class AdminLoginPage:
    """Encapsulates interactions with the custom Django admin login form."""

    def __init__(self, base_url: str, site_prefix: str) -> None:
        """
        Parameters
        ----------
        base_url:
            Root URL of the Django server (e.g. ``http://127.0.0.1:8000``).
        site_prefix:
            Admin site path prefix without trailing slash
            (e.g. ``"shop-admin"``, ``"social-admin"``).
        """
        self.login_url = f"{base_url}/{site_prefix}/login/"

    def goto(self, page: Page) -> None:
        """Navigate to the login page."""
        page.goto(self.login_url)

    def login(self, page: Page, email: str, password: str) -> None:
        """Fill in credentials and submit the login form."""
        page.goto(self.login_url)
        page.locator("#id_username").fill(email)
        page.locator("#id_password").fill(password)
        page.locator('[type="submit"]').click()

    def expect_logged_in(self, page: Page, site_prefix: str) -> None:
        """Assert that the browser was redirected to the admin index."""
        expect(page).to_have_url(re.compile(rf"/{re.escape(site_prefix)}/(?!.*login)"))

    def expect_error(self, page: Page, fragment: str) -> None:
        """Assert that an error message containing *fragment* is visible."""
        expect(page.locator(".errornote")).to_contain_text(fragment)

    def expect_on_login_page(self, page: Page) -> None:
        """Assert that the browser is still on (or was redirected to) the login page."""
        expect(page).to_have_url(re.compile(r"/login/"))

    def expect_forgot_password_link(self, page: Page) -> None:
        """Assert that the 'Mot de passe oublié ?' link is visible on the login page."""
        page.goto(self.login_url)
        expect(page.locator("#forgot-password-link")).to_be_visible()

    def goto_forgot_password(self, page: Page) -> None:
        """Click the forgot-password link and assert we land on the reset form."""
        page.goto(self.login_url)
        page.locator("#forgot-password-link").click()
        expect(page).to_have_url(re.compile(r"/auth/password_reset/"))

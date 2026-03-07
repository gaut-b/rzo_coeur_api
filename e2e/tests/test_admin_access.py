"""
test_admin_access.py

Verifies that the main Django admin (/admin/) blocks non-staff users.
A recipient (regular user with no is_staff flag) must not be able to
log in and should see an authentication error or be kept on the login page.
"""

import os

import pytest
from playwright.sync_api import Page

from e2e.conftest import E2E_PASSWORD
from e2e.pages.admin_login_page import AdminLoginPage

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8000")


@pytest.mark.usefixtures("django_server")
class TestMainAdminAccess:
    """Tests for the main /admin/ site access control."""

    def test_non_staff_user_cannot_access_main_admin(self, anon_page: Page) -> None:
        """
        A recipient (non-staff) must not be able to log into /admin/.
        Django's default admin redirects to /admin/login/ and shows an error
        for users without is_staff=True.
        """
        login_page = AdminLoginPage(BASE_URL, "admin")
        login_page.login(anon_page, "e2e-recipient@test.local", E2E_PASSWORD)

        # Django's built-in admin rejects non-staff with an error message
        # on the login page — it does not redirect them to the index.
        login_page.expect_error(
            anon_page,
            "Please enter the correct email address and password",
        )

    def test_unauthenticated_access_redirects_to_login(self, anon_page: Page) -> None:
        """Accessing /admin/ without a session redirects to /admin/login/."""
        anon_page.goto(f"{BASE_URL}/admin/")
        assert "/admin/login/" in anon_page.url

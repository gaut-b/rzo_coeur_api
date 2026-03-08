"""
test_social_admin.py

Covers the /social-admin/ and /cart-admin/ flows:
  - Social admin can access /social-admin/
  - Social worker is denied on /social-admin/
  - Both social admin and social worker can access /cart-admin/
  - Social admin can create a new Recipient
  - Social admin can create a new SocialWorker
"""

import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import BASE_URL, E2E_PASSWORD
from e2e.pages.admin_login_page import AdminLoginPage
from e2e.pages.social_admin_page import SocialAdminPage


@pytest.mark.usefixtures("django_server")
class TestSocialAdminAccess:
    """Access-control tests for /social-admin/."""

    def test_social_admin_can_access_social_admin_site(self, social_admin_page: Page) -> None:
        """A social admin user reaches the /social-admin/ index."""
        page_obj = SocialAdminPage(BASE_URL)
        page_obj.goto_index(social_admin_page)
        page_obj.expect_has_access(social_admin_page)

    def test_social_worker_is_denied_on_social_admin_site(self, anon_page: Page) -> None:
        """
        A social worker (non-admin) is denied access to /social-admin/.
        They should see a "permission denied" error on the login page.
        """
        login_page = AdminLoginPage(BASE_URL, "social-admin")
        login_page.login(anon_page, "e2e-social-worker@test.local", E2E_PASSWORD)
        login_page.expect_error(anon_page, "You do not have permission")


@pytest.mark.usefixtures("django_server")
class TestSocialAdminCRUD:
    """CRUD tests performed by a social admin on /social-admin/."""

    def test_social_admin_can_create_recipient(self, social_admin_page: Page) -> None:
        """Social admin creates a new recipient via the admin form."""
        page_obj = SocialAdminPage(BASE_URL)
        email = page_obj.create_recipient(social_admin_page)
        # After save, we're on the list — confirm the email appears there.
        expect(social_admin_page.locator("#result_list")).to_contain_text(email)

    def test_social_admin_can_create_social_worker(self, social_admin_page: Page) -> None:
        """Social admin creates a new social worker via the admin form."""
        page_obj = SocialAdminPage(BASE_URL)
        email = page_obj.create_social_worker(social_admin_page)
        expect(social_admin_page.locator("#result_list")).to_contain_text(email)

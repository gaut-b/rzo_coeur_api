"""
test_password_reset.py

Tests for the shared password-reset flow and the automatic welcome email
sent on user creation.

Covered scenarios:
  1. The "Mot de passe oublié ?" link is visible on every custom admin
     login page (social-admin, shop-admin, cart-admin).
  2. Submitting the reset form always shows the confirmation page — even
     for an unknown email address (no user enumeration).
  3. A password-reset email is delivered to Mailhog when a valid email is
     submitted; clients and recipients are silently blocked.
  4. The password field is absent from creation forms (backend generates it).
  5. A welcome email with a password-setup link is sent to Mailhog whenever
     a Recipient, SocialWorker or Cashier account is created.
  6. After setting a password, users are redirected to their correct
     interface (social admin, shop admin) or to the mobile deep link
     (recipients).
"""

import re
import time

import pytest
from playwright.sync_api import Page, expect

from e2e.conftest import BASE_URL, MAILHOG_API_URL
from e2e.pages.admin_login_page import AdminLoginPage
from e2e.pages.password_reset_page import PasswordResetPage
from e2e.pages.shop_admin_page import ShopAdminPage
from e2e.pages.social_admin_page import SocialAdminPage

# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _reset_page() -> PasswordResetPage:
    return PasswordResetPage(BASE_URL, MAILHOG_API_URL)


def _wait_for_email(reset_page: PasswordResetPage, email: str, timeout: float = 10.0) -> None:
    """
    Poll Mailhog until an email for *email* arrives or *timeout* expires.
    Uses a short sleep between retries to avoid hammering the API.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        messages = reset_page.get_messages_for(email)
        if messages:
            return
        time.sleep(0.5)
    pytest.fail(f"No email delivered to {email!r} in Mailhog within {timeout}s.")


def _assert_no_email_delivered(
    reset_page: PasswordResetPage,
    email: str,
    timeout: float = 3.0,
    poll_interval: float = 0.25,
) -> None:
    """
    Assert that no email is delivered to *email* within *timeout* seconds.

    Polls Mailhog every *poll_interval* seconds and fails immediately if any
    message arrives. Succeeds only after the full timeout elapses with no
    messages.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        messages = reset_page.get_messages_for(email)
        if messages:
            pytest.fail(
                f"Admin reset email must NOT be sent to {email!r}, but Mailhog received {len(messages)} message(s)."
            )
        time.sleep(poll_interval)


# ────────────────────────────────────────────────────────────────────────────
# 1 — "Mot de passe oublié ?" link visible on every custom admin login page
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("django_server")
class TestForgotPasswordLink:
    """The forgot-password link must be present on each custom admin login."""

    def test_link_visible_on_social_admin_login(self, anon_page: Page) -> None:
        """'Mot de passe oublié ?' is shown on the /social-admin/ login page."""
        login = AdminLoginPage(BASE_URL, "social-admin")
        login.expect_forgot_password_link(anon_page)

    def test_link_visible_on_shop_admin_login(self, anon_page: Page) -> None:
        """'Mot de passe oublié ?' is shown on the /shop-admin/ login page."""
        login = AdminLoginPage(BASE_URL, "shop-admin")
        login.expect_forgot_password_link(anon_page)

    def test_link_visible_on_cart_admin_login(self, anon_page: Page) -> None:
        """'Mot de passe oublié ?' is shown on the /cart-admin/ login page."""
        login = AdminLoginPage(BASE_URL, "cart-admin")
        login.expect_forgot_password_link(anon_page)

    def test_link_navigates_to_reset_form(self, anon_page: Page) -> None:
        """Clicking the link from the social-admin login lands on the reset form."""
        login = AdminLoginPage(BASE_URL, "social-admin")
        login.goto_forgot_password(anon_page)


# ────────────────────────────────────────────────────────────────────────────
# 2 & 3 — Password reset request flow
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("django_server")
class TestPasswordResetFlow:
    """End-to-end password-reset request flow."""

    def test_valid_email_shows_done_page(self, anon_page: Page) -> None:
        """Submitting the reset form with a known email shows the confirmation page."""
        reset = _reset_page()
        reset.submit_reset_request(anon_page, "e2e-social-admin@test.local")
        reset.expect_email_sent_confirmation(anon_page)

    def test_invalid_email_also_shows_done_page(self, anon_page: Page) -> None:
        """
        Submitting with an unknown email must also show the confirmation page
        (no user enumeration — Django's built-in behaviour).
        """
        reset = _reset_page()
        reset.submit_reset_request(anon_page, "nobody@unknown.invalid")
        reset.expect_email_sent_confirmation(anon_page)

    def test_valid_email_triggers_reset_email_in_mailhog(self, anon_page: Page) -> None:
        """
        After submitting the reset form for a real user, Mailhog must receive
        an email to that address containing a password-reset link.
        """
        email = "e2e-shop-manager@test.local"
        reset = _reset_page()
        reset.submit_reset_request(anon_page, email)
        reset.expect_email_sent_confirmation(anon_page)
        _wait_for_email(reset, email)
        reset.expect_reset_email_received(email)

    def test_client_email_does_not_trigger_reset_email(self, anon_page: Page) -> None:
        """
        Clients must be silently blocked from the admin reset flow.
        The done page still shows (no user enumeration) but Mailhog receives
        nothing.
        """
        email = "e2e-client@test.local"
        reset = _reset_page()
        reset.submit_reset_request(anon_page, email)
        reset.expect_email_sent_confirmation(anon_page)
        _assert_no_email_delivered(reset, email)

    def test_recipient_email_does_not_trigger_reset_email(self, anon_page: Page) -> None:
        """
        Recipients must be silently blocked from the admin reset flow.
        The done page still shows (no user enumeration) but Mailhog receives
        nothing.
        """
        email = "e2e-recipient@test.local"
        reset = _reset_page()
        reset.submit_reset_request(anon_page, email)
        reset.expect_email_sent_confirmation(anon_page)
        _assert_no_email_delivered(reset, email)


# ────────────────────────────────────────────────────────────────────────────
# 4 — No password field on creation forms
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("django_server")
class TestNoPasswordFieldOnCreationForms:
    """
    The password field must NOT appear on creation forms — passwords are
    generated automatically by the backend.
    """

    def test_no_password_field_on_recipient_form(self, social_admin_page: Page) -> None:
        """The recipient creation form has no password input."""
        page_obj = SocialAdminPage(BASE_URL)
        page_obj.goto_add_recipient(social_admin_page)
        expect(social_admin_page.locator("#id_password")).to_have_count(0)

    def test_no_password_field_on_social_worker_form(self, social_admin_page: Page) -> None:
        """The social worker creation form has no password input."""
        page_obj = SocialAdminPage(BASE_URL)
        page_obj.goto_add_social_worker(social_admin_page)
        expect(social_admin_page.locator("#id_password")).to_have_count(0)

    def test_no_password_field_on_cashier_form(self, shop_manager_page: Page) -> None:
        """The cashier creation form has no password input."""
        page_obj = ShopAdminPage(BASE_URL)
        page_obj.goto_add_cashier(shop_manager_page)
        expect(shop_manager_page.locator("#id_password")).to_have_count(0)

    def test_no_password_field_on_shop_manager_form(self, social_admin_page: Page) -> None:
        """The shop manager creation form (social admin) has no password input."""
        page_obj = SocialAdminPage(BASE_URL)
        page_obj.goto_add_shop_manager(social_admin_page)
        expect(social_admin_page.locator("#id_password")).to_have_count(0)


# ────────────────────────────────────────────────────────────────────────────
# 5 — Welcome email sent on account creation
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("django_server")
class TestWelcomeEmailOnAccountCreation:
    """
    After an admin creates a Recipient, SocialWorker or Cashier account,
    Mailhog must receive a welcome email containing a password-setup link.
    """

    def test_welcome_email_sent_on_recipient_creation(self, social_admin_page: Page) -> None:
        """Creating a Recipient triggers a welcome email via Mailhog."""
        reset = _reset_page()
        page_obj = SocialAdminPage(BASE_URL)
        email = page_obj.create_recipient(social_admin_page)
        _wait_for_email(reset, email)
        reset.expect_welcome_email_received(email)

    def test_welcome_email_sent_on_social_worker_creation(self, social_admin_page: Page) -> None:
        """Creating a SocialWorker triggers a welcome email via Mailhog."""
        reset = _reset_page()
        page_obj = SocialAdminPage(BASE_URL)
        email = page_obj.create_social_worker(social_admin_page)
        _wait_for_email(reset, email)
        reset.expect_welcome_email_received(email)

    def test_welcome_email_sent_on_cashier_creation(self, shop_manager_page: Page) -> None:
        """Creating a Cashier triggers a welcome email via Mailhog."""
        reset = _reset_page()
        page_obj = ShopAdminPage(BASE_URL)
        email = page_obj.create_cashier(shop_manager_page, role="False")
        _wait_for_email(reset, email)
        reset.expect_welcome_email_received(email)

    def test_welcome_email_sent_on_shop_manager_creation(self, social_admin_page: Page) -> None:
        """Creating a Shop Manager from social admin triggers a welcome email via Mailhog."""
        reset = _reset_page()
        page_obj = SocialAdminPage(BASE_URL)
        email = page_obj.create_shop_manager(social_admin_page)
        _wait_for_email(reset, email)
        reset.expect_welcome_email_received(email)


# ────────────────────────────────────────────────────────────────────────────
# 6 — Post-password-set redirect respects callbackUrl
# ────────────────────────────────────────────────────────────────────────────


def _set_password_via_link(page: Page, reset_url: str, new_password: str) -> None:
    """
    Navigate to *reset_url*, fill both password fields and submit.
    Asserts the form page is reachable (valid link).
    """
    page.goto(reset_url)
    # Django redirects /auth/reset/<uid>/<token>/ to /auth/reset/<uid>/set-password/
    # once it validates the token; wait for that.
    page.wait_for_url(re.compile(r"/auth/reset/.*/(set-password|done)/"), timeout=10_000)
    if "set-password" in page.url:
        page.locator("#id_new_password1").fill(new_password)
        page.locator("#id_new_password2").fill(new_password)
        page.locator('[type="submit"]').click()


@pytest.mark.usefixtures("django_server")
class TestPostPasswordSetRedirect:
    """
    After setting a password via a welcome / reset email link, each user
    type must be redirected to the correct destination.
    """

    def test_social_worker_redirected_to_social_admin(self, social_admin_page: Page, anon_page: Page) -> None:
        """
        A newly created social worker clicks the welcome email link and, after
        setting their password, lands on /social-admin/login/.
        """
        reset = _reset_page()
        page_obj = SocialAdminPage(BASE_URL)
        email = page_obj.create_social_worker(social_admin_page)
        _wait_for_email(reset, email)

        reset_url = reset.extract_reset_url_from_email(email)
        _set_password_via_link(anon_page, reset_url, "NewPassTest123!")
        expect(anon_page).to_have_url(re.compile(r"/social-admin/login/"))

    def test_cashier_redirected_to_shop_admin(self, shop_manager_page: Page, anon_page: Page) -> None:
        """
        A newly created cashier clicks the welcome email link and, after
        setting their password, lands on /shop-admin/login/.
        """
        reset = _reset_page()
        page_obj = ShopAdminPage(BASE_URL)
        email = page_obj.create_cashier(shop_manager_page, role="False")
        _wait_for_email(reset, email)

        reset_url = reset.extract_reset_url_from_email(email)
        _set_password_via_link(anon_page, reset_url, "NewPassTest123!")
        expect(anon_page).to_have_url(re.compile(r"/shop-admin/login/"))

    def test_recipient_welcome_link_contains_mobile_callback(self, social_admin_page: Page) -> None:
        """
        The welcome email link for a recipient must carry the mobile deep link
        as its callbackUrl parameter.  The browser cannot follow a deep link,
        so we only assert that the URL contains the expected callbackUrl value.
        """
        reset = _reset_page()
        page_obj = SocialAdminPage(BASE_URL)
        email = page_obj.create_recipient(social_admin_page)
        _wait_for_email(reset, email)

        reset_url = reset.extract_reset_url_from_email(email)
        mobile_scheme = "rzo-coeur-mobile-app"
        assert (
            f"callbackUrl={mobile_scheme}%3A%2F%2Fsign-in" in reset_url
            or f"callbackUrl={mobile_scheme}://sign-in" in reset_url
        ), (
            f"Recipient welcome email reset URL does not contain the mobile deep link "
            f"as callbackUrl. URL: {reset_url!r}"
        )

    def test_forgot_password_respects_callback_url(self, shop_manager_page: Page, anon_page: Page) -> None:
        """
        When 'Mot de passe oublié ?' is clicked from /shop-admin/login/, the
        reset email link must carry callbackUrl=/shop-admin/login/, and after
        setting the password the user lands on /shop-admin/login/.

        A fresh cashier is created for this test so that no seeded account is
        mutated.
        """
        # Create a disposable cashier whose password we can safely change.
        shop_obj = ShopAdminPage(BASE_URL)
        email = shop_obj.create_cashier(shop_manager_page, role="False")

        reset = _reset_page()
        reset.clear_mailhog()  # discard the welcome email for the new cashier

        # Submit via the shop-admin forgot-password link (carries callbackUrl).
        anon_page.goto(f"{BASE_URL}/auth/password_reset/?callbackUrl=/shop-admin/login/")
        anon_page.locator("#id_email").fill(email)
        anon_page.locator('[type="submit"]').click()
        reset.expect_email_sent_confirmation(anon_page)

        _wait_for_email(reset, email)
        reset_url = reset.extract_reset_url_from_email(email)
        assert "callbackUrl" in reset_url, f"Reset URL does not contain callbackUrl: {reset_url!r}"
        _set_password_via_link(anon_page, reset_url, "NewPassTest123!")
        expect(anon_page).to_have_url(re.compile(r"/shop-admin/login/"))

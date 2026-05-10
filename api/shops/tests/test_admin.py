"""
Tests for custom admin site authentication and authorization.
"""

from django.contrib.auth.models import AnonymousUser
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from api.models import Cashier, CustomUser, Shop, SocialCenter
from api.shops.admin import shop_admin_site


class CustomAdminSiteTests(TestCase):
    """Test custom admin site authentication and authorization."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.client = Client()

        # Create social center and shop
        self.social_center = SocialCenter.objects.create(name="Test Social Center", mail="test@socialcenter.com")
        self.shop = Shop.objects.create(name="Test Shop", social_center=self.social_center)

        # Create users with different roles
        self.cashier_user = CustomUser.objects.create_user(
            email="cashier@test.com", password="testpass123", first_name="Test", last_name="Cashier"
        )
        self.cashier = Cashier.objects.create(user=self.cashier_user, shop=self.shop, is_shop_manager=False)

        self.manager_user = CustomUser.objects.create_user(
            email="manager@test.com", password="testpass123", first_name="Test", last_name="Manager"
        )
        self.manager = Cashier.objects.create(user=self.manager_user, shop=self.shop, is_shop_manager=True)

        self.regular_user = CustomUser.objects.create_user(
            email="regular@test.com", password="testpass123", first_name="Regular", last_name="User"
        )

        self.inactive_user = CustomUser.objects.create_user(
            email="inactive@test.com", password="testpass123", first_name="Inactive", last_name="User", is_active=False
        )
        self.inactive_cashier = Cashier.objects.create(user=self.inactive_user, shop=self.shop, is_shop_manager=False)

    def test_invalid_credentials(self):
        """Test that invalid credentials show appropriate error."""
        response = self.client.post(
            reverse("shop_admin:login"),
            {
                "username": "cashier@test.com",
                "password": "wrongpassword",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Veuillez saisir une adresse e-mail et un mot de passe corrects.")

    def test_inactive_user_denied(self):
        """Test that inactive users cannot log in."""
        response = self.client.post(
            reverse("shop_admin:login"),
            {
                "username": "inactive@test.com",
                "password": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Veuillez saisir une adresse e-mail et un mot de passe corrects.")

    def test_valid_next_url_redirect(self):
        """Test that valid 'next' parameter redirects correctly."""
        response = self.client.post(
            reverse("shop_admin:login") + "?next=/shop-admin/api/article/",
            {
                "username": "cashier@test.com",
                "password": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/shop-admin/api/article/")

    def test_external_next_url_rejected(self):
        """Test that external URLs in 'next' parameter are rejected."""
        response = self.client.post(
            reverse("shop_admin:login") + "?next=https://evil.com/phishing",
            {
                "username": "cashier@test.com",
                "password": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 302)
        # Should redirect to admin index, not external URL
        self.assertTrue(response.url.startswith("/shop-admin/"))
        self.assertNotIn("evil.com", response.url)

    def test_next_url_different_host_rejected(self):
        """Test that 'next' URLs with different hosts are rejected."""
        response = self.client.post(
            reverse("shop_admin:login") + "?next=http://different-host.com/admin/",
            {
                "username": "cashier@test.com",
                "password": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("different-host.com", response.url)

    def test_next_url_from_post_data(self):
        """Test that 'next' parameter from POST data works correctly."""
        response = self.client.post(
            reverse("shop_admin:login"),
            {
                "username": "cashier@test.com",
                "password": "testpass123",
                "next": "/shop-admin/api/cashier/",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/shop-admin/api/cashier/")

    def test_login_get_request_shows_form(self):
        """Test that GET request to login shows the login form."""
        response = self.client.get(reverse("shop_admin:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connexion — Admin magasin")

    def test_has_permission_inactive_user(self):
        """Test has_permission returns False for inactive user."""
        request = self.factory.get("/shop-admin/")
        request.user = self.inactive_user
        self.assertFalse(shop_admin_site.has_permission(request))

    def test_has_permission_unauthenticated(self):
        """Test has_permission returns False for unauthenticated user."""
        request = self.factory.get("/shop-admin/")
        request.user = AnonymousUser()
        self.assertFalse(shop_admin_site.has_permission(request))

    def test_user_loses_cashier_role_loses_access(self):
        """Test that user loses access when cashier profile is deleted."""
        # Log in as cashier
        self.client.login(username="cashier@test.com", password="testpass123")

        # Verify can access shop admin
        response = self.client.get("/shop-admin/")
        self.assertEqual(response.status_code, 200)

        # Remove cashier profile
        self.cashier.delete()

        # Verify can no longer access shop admin
        response = self.client.get("/shop-admin/")
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_login_preserves_username_on_error(self):
        """Test that username is preserved in form when login fails."""
        response = self.client.post(
            reverse("shop_admin:login"),
            {
                "username": "cashier@test.com",
                "password": "wrongpassword",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cashier@test.com")

    def test_login_csrf_protection(self):
        """Test that login is protected against CSRF attacks."""
        # Attempt login without CSRF token
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            reverse("shop_admin:login"),
            {
                "username": "cashier@test.com",
                "password": "testpass123",
            },
        )
        # Should be rejected due to missing CSRF token
        self.assertEqual(response.status_code, 403)

    def test_never_cache_decorator_applied(self):
        """Test that login view has cache-control headers."""
        response = self.client.get(reverse("shop_admin:login"))
        self.assertIn("no-cache", response.get("Cache-Control", "").lower())


class ShopAdminAccessControlTests(TestCase):
    """Test access control for shop admin models."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()

        # Create shops
        self.social_center = SocialCenter.objects.create(name="Test Social Center", mail="test@socialcenter.com")
        self.shop1 = Shop.objects.create(name="Shop 1", social_center=self.social_center)
        self.shop2 = Shop.objects.create(name="Shop 2", social_center=self.social_center)

        # Create manager for shop1
        self.manager1_user = CustomUser.objects.create_user(email="manager1@test.com", password="testpass123")
        self.manager1 = Cashier.objects.create(user=self.manager1_user, shop=self.shop1, is_shop_manager=True)

        # Create cashier for shop1
        self.cashier1_user = CustomUser.objects.create_user(email="cashier1@test.com", password="testpass123")
        self.cashier1 = Cashier.objects.create(user=self.cashier1_user, shop=self.shop1, is_shop_manager=False)

        # Create manager for shop2
        self.manager2_user = CustomUser.objects.create_user(email="manager2@test.com", password="testpass123")
        self.manager2 = Cashier.objects.create(user=self.manager2_user, shop=self.shop2, is_shop_manager=True)

    def test_manager_can_view_own_shop_cashiers(self):
        """Test that manager can only view cashiers from their shop."""
        self.client.login(username="manager1@test.com", password="testpass123")
        response = self.client.get("/shop-admin/api/cashier/")
        self.assertEqual(response.status_code, 200)
        # Should see cashiers from shop1 only
        self.assertContains(response, "cashier1@test.com")
        self.assertNotContains(response, "manager2@test.com")

    def test_cashier_cannot_view_cashier_list(self):
        """Test that regular cashiers cannot access cashier management."""
        self.client.login(username="cashier1@test.com", password="testpass123")
        response = self.client.get("/shop-admin/api/cashier/")
        # Should be forbidden or redirect
        self.assertIn(response.status_code, [302, 403])

    def test_manager_cannot_view_other_shop_cashiers(self):
        """Test that manager cannot view cashiers from other shops."""
        self.client.login(username="manager1@test.com", password="testpass123")
        # Try to access cashier from shop2
        response = self.client.get(f"/shop-admin/api/cashier/{self.manager2.pk}/change/")
        # Should be forbidden or not found
        self.assertIn(response.status_code, [302, 403, 404])

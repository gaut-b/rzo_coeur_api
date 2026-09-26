"""Tests for self-service account deletion (DELETE /api/auth/user/)."""

from rest_framework import status
from rest_framework.test import APITestCase

from api.enums import UserRole
from api.models import Cashier, Client, CustomUser, Recipient, Shop, SocialCenter, SocialWorker


class AccountDeletionPermissionTests(APITestCase):
    """Role-based access checks for the delete-account endpoint."""

    def setUp(self):
        self.social_center = SocialCenter.objects.create(
            name="Centre Social Test",
            street_number="123",
            street_name="Rue Test",
            postal_code="75001",
            city="Paris",
            mail="centre@test.com",
        )
        self.shop = Shop.objects.create(
            name="Magasin Test",
            street_number="456",
            street_name="Avenue Test",
            postal_code="75002",
            city="Paris",
            social_center=self.social_center,
        )

    def test_cashier_cannot_self_delete(self):
        user = CustomUser.objects.create_user(email="cashier@test.com", password="testpass123")
        Cashier.objects.create(user=user, shop=self.shop)

        self.client.force_authenticate(user=user)
        response = self.client.delete("/api/auth/user/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_social_worker_cannot_self_delete(self):
        user = CustomUser.objects.create_user(email="sw@test.com", password="testpass123")
        SocialWorker.objects.create(user=user, social_center=self.social_center)

        self.client.force_authenticate(user=user)
        response = self.client.delete("/api/auth/user/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.delete("/api/auth/user/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AccountDeletionAnonymizationTests(APITestCase):
    """Verifies anonymization behavior and that history is preserved."""

    def setUp(self):
        self.social_center = SocialCenter.objects.create(
            name="Centre Social Test",
            street_number="123",
            street_name="Rue Test",
            postal_code="75001",
            city="Paris",
            mail="centre@test.com",
        )
        self.shop = Shop.objects.create(
            name="Magasin Test",
            street_number="456",
            street_name="Avenue Test",
            postal_code="75002",
            city="Paris",
            social_center=self.social_center,
        )

    def test_client_delete_anonymizes_and_keeps_articles(self):
        user = CustomUser.objects.create_user(
            email="client@test.com", password="testpass123", first_name="John", last_name="Doe"
        )
        client_profile = Client.objects.create(user=user)
        article = client_profile.articles.create(name="Pâtes", barcode=123456, shop=self.shop)

        self.client.force_authenticate(user=user)
        response = self.client.delete("/api/auth/user/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertNotEqual(user.email, "client@test.com")
        self.assertEqual(user.first_name, "")
        self.assertEqual(user.last_name, "")
        self.assertFalse(user.has_usable_password())

        # History is preserved: profile and article rows still exist.
        self.assertTrue(Client.objects.filter(pk=user.pk).exists())
        article.refresh_from_db()
        self.assertEqual(article.client_id, user.pk)

    def test_recipient_delete_anonymizes_and_keeps_carts(self):
        user = CustomUser.objects.create_user(email="recipient@test.com", password="testpass123")
        recipient = Recipient.objects.create(user=user, social_center=self.social_center)
        cart = recipient.carts.create(shop=self.shop)

        self.client.force_authenticate(user=user)
        response = self.client.delete("/api/auth/user/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        user.refresh_from_db()
        self.assertFalse(user.is_active)

        # History is preserved: profile and cart rows still exist.
        self.assertTrue(Recipient.objects.filter(pk=user.pk).exists())
        cart.refresh_from_db()
        self.assertEqual(cart.recipient_id, user.pk)

    def test_deleted_account_is_locked_out_after_real_login(self):
        """After deletion, the JWT cookies issued at login can no longer authenticate."""
        CustomUser.objects.create_user(email="client2@test.com", password="testpass123")
        Client.objects.create(user=CustomUser.objects.get(email="client2@test.com"))

        login_response = self.client.post(
            "/api/auth/login/",
            {"email": "client2@test.com", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        delete_response = self.client.delete("/api/auth/user/")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(delete_response.cookies["auth-jwt"].value, "")

        # The same session cookies (now cleared) can no longer access the API.
        me_response = self.client.get("/api/auth/user/")
        self.assertEqual(me_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_role_is_preserved_across_anonymization(self):
        """Sanity check that role lookup still works right after anonymizing."""
        user = CustomUser.objects.create_user(email="client3@test.com", password="testpass123")
        Client.objects.create(user=user)

        self.client.force_authenticate(user=user)
        self.client.delete("/api/auth/user/")

        user.refresh_from_db()
        self.assertEqual(user.role, UserRole.CLIENT.value)

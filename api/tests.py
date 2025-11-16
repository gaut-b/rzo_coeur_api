from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .constants import MAX_ARTICLES_PER_REQUEST
from .enums import CartStatus, UserRole
from .models import (
    Article,
    Cart,
    Cashier,
    Client,
    CustomUser,
    Recipient,
    Shop,
    SocialCenter,
    SocialWorker,
)


class UsersManagersTests(TestCase):

    def test_create_user(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(email="normal@user.com", password="foo")
        self.assertEqual(user.email, "normal@user.com")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        try:
            # username is None for the AbstractUser option
            # username does not exist for the AbstractBaseUser option
            self.assertIsNone(user.username)
        except AttributeError:
            pass
        with self.assertRaises(TypeError):
            user_model.objects.create_user()
        with self.assertRaises(TypeError):
            user_model.objects.create_user(email="")
        with self.assertRaises(ValueError):
            user_model.objects.create_user(email="", password="foo")

    def test_create_superuser(self):
        user_model = get_user_model()
        admin_user = user_model.objects.create_superuser(email="super@user.com", password="foo")
        self.assertEqual(admin_user.email, "super@user.com")
        self.assertTrue(admin_user.is_active)
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        try:
            # username is None for the AbstractUser option
            # username does not exist for the AbstractBaseUser option
            self.assertIsNone(admin_user.username)
        except AttributeError:
            pass
        with self.assertRaises(ValueError):
            user_model.objects.create_superuser(
                email="super@user.com", password="foo", is_superuser=False
            )


class CustomUserSerializerTests(APITestCase):
    """Tests for the CustomUserSerializer with role field."""

    def setUp(self):
        """Set up test data for serializer tests."""
        # Import here to avoid circular import
        from .serializers import CustomUserSerializer

        self.CustomUserSerializer = CustomUserSerializer

        # Create a social center for social workers and recipients
        self.social_center = SocialCenter.objects.create(
            name="Centre Social Test", address="123 Rue Test", mail="centre@test.com"
        )

        # Create a shop for cashiers
        self.shop = Shop.objects.create(
            name="Magasin Test", address="456 Avenue Test", social_center=self.social_center
        )

    def test_serialize_user_without_role(self):
        """Test serialization of a user without any role."""
        user = CustomUser.objects.create_user(
            email="norole@test.com", password="testpass123", first_name="Sans", last_name="Role"
        )

        serializer = self.CustomUserSerializer(user)
        data = serializer.data

        self.assertEqual(data["email"], "norole@test.com")
        self.assertEqual(data["first_name"], "Sans")
        self.assertEqual(data["last_name"], "Role")
        self.assertIsNone(data["role"])

    def test_serialize_client(self):
        """Test serialization of a user with CLIENT role."""
        user = CustomUser.objects.create_user(
            email="client@test.com", password="testpass123", first_name="Client", last_name="Test"
        )
        Client.objects.create(user=user)

        serializer = self.CustomUserSerializer(user)
        data = serializer.data

        self.assertEqual(data["email"], "client@test.com")
        self.assertEqual(data["role"], UserRole.CLIENT.value)

    def test_serialize_social_worker(self):
        """Test serialization of a user with SOCIAL_WORKER role."""
        user = CustomUser.objects.create_user(
            email="socialworker@test.com",
            password="testpass123",
            first_name="Travailleur",
            last_name="Social",
        )
        SocialWorker.objects.create(user=user, social_center=self.social_center)

        serializer = self.CustomUserSerializer(user)
        data = serializer.data

        self.assertEqual(data["email"], "socialworker@test.com")
        self.assertEqual(data["role"], UserRole.SOCIAL_WORKER.value)

    def test_serialize_recipient(self):
        """Test serialization of a user with RECIPIENT role."""
        user = CustomUser.objects.create_user(
            email="recipient@test.com",
            password="testpass123",
            first_name="Beneficiaire",
            last_name="Test",
        )
        Recipient.objects.create(user=user, social_center=self.social_center)

        serializer = self.CustomUserSerializer(user)
        data = serializer.data

        self.assertEqual(data["email"], "recipient@test.com")
        self.assertEqual(data["role"], UserRole.RECIPIENT.value)

    def test_serialize_cashier(self):
        """Test serialization of a user with CASHIER role."""
        user = CustomUser.objects.create_user(
            email="cashier@test.com",
            password="testpass123",
            first_name="Caissier",
            last_name="Test",
        )
        Cashier.objects.create(user=user, shop=self.shop)

        serializer = self.CustomUserSerializer(user)
        data = serializer.data

        self.assertEqual(data["email"], "cashier@test.com")
        self.assertEqual(data["role"], UserRole.CASHIER.value)

    def test_role_field_is_read_only(self):
        """Test that the role field cannot be set during deserialization."""
        data = {
            "email": "newuser@test.com",
            "password": "testpass123",
            "first_name": "New",
            "last_name": "User",
            "role": UserRole.CLIENT.value,  # Should be ignored
        }

        serializer = self.CustomUserSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # The role field should not be writable
        self.assertNotIn("role", serializer.validated_data)


class ArticleCreateViewTests(APITestCase):
    """Tests for the ArticleCreateView endpoint."""

    def setUp(self):
        """Set up test data for article creation tests."""
        # Create social center
        self.social_center = SocialCenter.objects.create(
            name="Centre Social Test", address="123 Rue Test", mail="centre@test.com"
        )

        # Create shop
        self.shop = Shop.objects.create(
            name="Magasin Test", address="456 Avenue Test", social_center=self.social_center
        )

        # Create cashier user
        self.cashier_user = CustomUser.objects.create_user(
            email="cashier@test.com",
            password="testpass123",
            first_name="Caissier",
            last_name="Test",
        )
        self.cashier = Cashier.objects.create(user=self.cashier_user, shop=self.shop)

        # Create client user
        self.client_user = CustomUser.objects.create_user(
            email="client@test.com", password="testpass123", first_name="Client", last_name="Test"
        )
        self.client = Client.objects.create(user=self.client_user)

        # Create other role users for permission testing
        self.social_worker_user = CustomUser.objects.create_user(
            email="socialworker@test.com",
            password="testpass123",
            first_name="Travailleur",
            last_name="Social",
        )
        SocialWorker.objects.create(user=self.social_worker_user, social_center=self.social_center)

        self.recipient_user = CustomUser.objects.create_user(
            email="recipient@test.com",
            password="testpass123",
            first_name="Beneficiaire",
            last_name="Test",
        )
        Recipient.objects.create(user=self.recipient_user, social_center=self.social_center)

        # API client
        self.api_client = APIClient()
        self.url = "/api/articles/"

    def test_create_articles_success(self):
        """Test successful bulk article creation by a cashier."""
        self.api_client.force_authenticate(user=self.cashier_user)

        data = {
            "client_id": self.client.pk,
            "articles": [
                {"barcode": 3017620422003},
                {"barcode": 3564700013151},
                {"barcode": 3270190207092},
            ],
        }

        response = self.api_client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("message", response.data)
        self.assertIn("articles", response.data)
        self.assertEqual(len(response.data["articles"]), 3)

        # Verify articles were created in database
        self.assertEqual(Article.objects.count(), 3)
        article = Article.objects.first()
        self.assertEqual(article.client, self.client)
        self.assertEqual(article.shop, self.shop)
        self.assertIsNone(article.cart)

    def test_create_articles_unauthenticated(self):
        """Test that unauthenticated users cannot create articles."""
        data = {
            "client_id": self.client.pk,
            "articles": [{"barcode": 3017620422003}],
        }

        response = self.api_client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Article.objects.count(), 0)

    def test_create_articles_non_cashier_user(self):
        """Test that non-cashier users (social worker, recipient, client) cannot create articles."""
        # Test with social worker
        self.api_client.force_authenticate(user=self.social_worker_user)
        data = {
            "client_id": self.client.pk,
            "articles": [{"barcode": 3017620422003}],
        }
        response = self.api_client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Test with recipient
        self.api_client.force_authenticate(user=self.recipient_user)
        response = self.api_client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Test with client
        self.api_client.force_authenticate(user=self.client_user)
        response = self.api_client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.assertEqual(Article.objects.count(), 0)

    def test_create_articles_invalid_client_id(self):
        """Test that invalid client_id returns 400 error."""
        self.api_client.force_authenticate(user=self.cashier_user)

        data = {
            "client_id": 99999,  # Non-existent client
            "articles": [{"barcode": 3017620422003}],
        }

        response = self.api_client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("client_id", response.data)
        self.assertEqual(Article.objects.count(), 0)

    def test_create_articles_client_id_not_client_role(self):
        """Test that client_id must correspond to a Client, not another role type."""
        self.api_client.force_authenticate(user=self.cashier_user)

        # Try to use a SocialWorker's ID as client_id
        # This should fail because socialworker.pk is not a valid Client ID
        data = {
            "client_id": self.social_worker_user.socialworker.pk,
            "articles": [{"barcode": 3017620422003}],
        }

        response = self.api_client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("client_id", response.data)
        self.assertEqual(Article.objects.count(), 0)

    def test_create_articles_empty_list(self):
        """Test that empty articles list returns 400 error."""
        self.api_client.force_authenticate(user=self.cashier_user)

        data = {
            "client_id": self.client.pk,
            "articles": [],  # Empty list
        }

        response = self.api_client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("articles", response.data)
        self.assertEqual(Article.objects.count(), 0)

    def test_create_articles_exceeds_max_limit(self):
        """Test that exceeding the configured MAX_ARTICLES_PER_REQUEST limit returns 400 error."""
        self.api_client.force_authenticate(user=self.cashier_user)

        # Create MAX_ARTICLES_PER_REQUEST + 1 articles (exceeds limit)
        articles_list = [
            {"barcode": 3017620422003 + i} for i in range(MAX_ARTICLES_PER_REQUEST + 1)
        ]

        data = {
            "client_id": self.client.pk,
            "articles": articles_list,
        }

        response = self.api_client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("articles", response.data)
        self.assertEqual(Article.objects.count(), 0)

    def test_create_articles_at_max_limit(self):
        """Test that creating exactly MAX_ARTICLES_PER_REQUEST articles works."""
        self.api_client.force_authenticate(user=self.cashier_user)

        # Create exactly MAX_ARTICLES_PER_REQUEST articles
        articles_list = [{"barcode": 3017620422003 + i} for i in range(MAX_ARTICLES_PER_REQUEST)]

        data = {
            "client_id": self.client.pk,
            "articles": articles_list,
        }

        response = self.api_client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Article.objects.count(), MAX_ARTICLES_PER_REQUEST)

    def test_create_articles_invalid_barcode(self):
        """Test that invalid barcode format returns 400 error."""
        self.api_client.force_authenticate(user=self.cashier_user)

        data = {
            "client_id": self.client.pk,
            "articles": [{"barcode": -123}],  # Negative barcode
        }

        response = self.api_client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Article.objects.count(), 0)

    def test_create_articles_missing_required_fields(self):
        """Test that missing required fields returns 400 error."""
        self.api_client.force_authenticate(user=self.cashier_user)

        # Missing client_id
        data = {
            "articles": [{"barcode": 3017620422003}],
        }
        response = self.api_client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Missing articles
        data = {
            "client_id": self.client.pk,
        }
        response = self.api_client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(Article.objects.count(), 0)


class CartCollectViewTests(APITestCase):
    """Test suite for the CartCollectView endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        # Create social center
        self.social_center = SocialCenter.objects.create(
            name="Centre Social Test",
            address="123 Rue Test",
            mail="centre@test.com",
        )

        # Create shops
        self.shop1 = Shop.objects.create(
            name="Magasin Test 1",
            address="456 Avenue Test",
            social_center=self.social_center,
        )
        self.shop2 = Shop.objects.create(
            name="Magasin Test 2",
            address="789 Boulevard Test",
            social_center=self.social_center,
        )

        # Create cashier user and cashier for shop1
        self.cashier_user = CustomUser.objects.create_user(
            email="cashier@test.com",
            password="testpass123",
            first_name="Caissier",
            last_name="Test",
        )
        self.cashier = Cashier.objects.create(
            user=self.cashier_user,
            shop=self.shop1,
        )

        # Create another cashier for shop2
        self.cashier2_user = CustomUser.objects.create_user(
            email="cashier2@test.com",
            password="testpass123",
            first_name="Caissier2",
            last_name="Test",
        )
        self.cashier2 = Cashier.objects.create(
            user=self.cashier2_user,
            shop=self.shop2,
        )

        # Create recipient user and recipient
        self.recipient_user = CustomUser.objects.create_user(
            email="recipient@test.com",
            password="testpass123",
            first_name="Bénéficiaire",
            last_name="Test",
        )
        self.recipient = Recipient.objects.create(
            user=self.recipient_user,
            social_center=self.social_center,
        )

        # Create another recipient
        self.recipient2_user = CustomUser.objects.create_user(
            email="recipient2@test.com",
            password="testpass123",
            first_name="Bénéficiaire2",
            last_name="Test",
        )
        self.recipient2 = Recipient.objects.create(
            user=self.recipient2_user,
            social_center=self.social_center,
        )

        # Create a cart in ASSIGNED status
        self.cart_assigned = Cart.objects.create(
            shop=self.shop1,
            recipient=self.recipient,
            status=CartStatus.ASSIGNED.value,
        )

        # Create a cart in PENDING status
        self.cart_pending = Cart.objects.create(
            shop=self.shop1,
            recipient=self.recipient,
            status=CartStatus.PENDING.value,
        )

        # Create a cart already COLLECTED
        self.cart_collected = Cart.objects.create(
            shop=self.shop1,
            recipient=self.recipient,
            status=CartStatus.COLLECTED.value,
        )

        # Create a cart for shop2
        self.cart_shop2 = Cart.objects.create(
            shop=self.shop2,
            recipient=self.recipient,
            status=CartStatus.ASSIGNED.value,
        )

        # Create client user (for permission tests)
        self.client_user = CustomUser.objects.create_user(
            email="client@test.com",
            password="testpass123",
            first_name="Client",
            last_name="Test",
        )
        self.client = Client.objects.create(user=self.client_user)

        self.api_client = APIClient()

    def test_collect_cart_success(self):
        """Test successful cart collection."""
        self.api_client.force_authenticate(user=self.cashier_user)
        url = f"/api/recipients/{self.recipient.user.pk}/carts/{self.cart_assigned.id}/collect/"
        data = {}

        response = self.api_client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
        self.assertIn("cart", response.data)
        self.assertEqual(response.data["cart"]["status"], CartStatus.COLLECTED.value)
        self.assertIsNotNone(response.data["cart"]["collected_at"])

        # Verify database update
        self.cart_assigned.refresh_from_db()
        self.assertEqual(self.cart_assigned.status, CartStatus.COLLECTED.value)
        self.assertIsNotNone(self.cart_assigned.collected_at)

    def test_collect_cart_unauthenticated(self):
        """Test that unauthenticated users cannot collect carts."""
        url = f"/api/recipients/{self.recipient.user.pk}/carts/{self.cart_assigned.id}/collect/"
        data = {}

        response = self.api_client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_collect_cart_non_cashier(self):
        """Test that non-cashier users cannot collect carts."""
        self.api_client.force_authenticate(user=self.client_user)
        url = f"/api/recipients/{self.recipient.user.pk}/carts/{self.cart_assigned.id}/collect/"
        data = {}

        response = self.api_client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_collect_cart_not_found(self):
        """Test collecting a non-existent cart."""
        self.api_client.force_authenticate(user=self.cashier_user)
        url = f"/api/recipients/{self.recipient.user.pk}/carts/99999/collect/"
        data = {}

        response = self.api_client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_collect_cart_pending_status(self):
        """Test that carts in PENDING status cannot be collected."""
        self.api_client.force_authenticate(user=self.cashier_user)
        url = f"/api/recipients/{self.recipient.user.pk}/carts/{self.cart_pending.id}/collect/"
        data = {}

        response = self.api_client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_collect_cart_already_collected(self):
        """Test that already collected carts cannot be collected again."""
        self.api_client.force_authenticate(user=self.cashier_user)
        url = f"/api/recipients/{self.recipient.user.pk}/carts/{self.cart_collected.id}/collect/"
        data = {}

        response = self.api_client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_collect_cart_wrong_shop(self):
        """Test that cashiers can only collect carts from their shop."""
        self.api_client.force_authenticate(user=self.cashier_user)
        url = f"/api/recipients/{self.recipient.user.pk}/carts/{self.cart_shop2.id}/collect/"
        data = {}

        response = self.api_client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("shop", response.data)

    def test_collect_cart_recipient_mismatch(self):
        """Test that recipient_id must match the cart's recipient."""
        self.api_client.force_authenticate(user=self.cashier_user)
        url = f"/api/recipients/{self.recipient2.user.pk}/carts/{self.cart_assigned.id}/collect/"
        data = {}

        response = self.api_client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("recipient", response.data)

    def test_collect_cart_invalid_recipient_id(self):
        """Test with non-existent recipient ID."""
        self.api_client.force_authenticate(user=self.cashier_user)
        url = f"/api/recipients/99999/carts/{self.cart_assigned.id}/collect/"
        data = {}

        response = self.api_client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_collect_cart_missing_recipient_id(self):
        """Test with missing recipient_id in request (now handled by URL)."""
        self.api_client.force_authenticate(user=self.cashier_user)
        url = f"/api/recipients/{self.recipient.user.pk}/carts/{self.cart_assigned.id}/collect/"
        data = {}

        response = self.api_client.patch(url, data, format="json")

        # Should succeed since recipient_id is now in URL
        self.assertEqual(response.status_code, status.HTTP_200_OK)

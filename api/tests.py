from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
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
        user = user_model.objects.create_user(  # type: ignore[attr-defined]
            email="normal@user.com", password="foo"
        )
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
            user_model.objects.create_user()  # type: ignore[attr-defined]
        with self.assertRaises(TypeError):
            user_model.objects.create_user(email="")  # type: ignore[attr-defined]
        with self.assertRaises(ValueError):
            user_model.objects.create_user(email="", password="foo")  # type: ignore[attr-defined]

    def test_create_superuser(self):
        user_model = get_user_model()
        admin_user = user_model.objects.create_superuser(  # type: ignore[attr-defined]
            email="super@user.com", password="foo"
        )
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
            user_model.objects.create_superuser(  # type: ignore[attr-defined]
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
            name="Centre Social Test",
            street_number="123",
            street_name="Rue Test",
            postal_code="75001",
            city="Paris",
            mail="centre@test.com",
        )

        # Create a shop for cashiers
        self.shop = Shop.objects.create(
            name="Magasin Test",
            street_number="456",
            street_name="Avenue Test",
            postal_code="75002",
            city="Paris",
            social_center=self.social_center,
        )

    def test_serialize_user_without_role(self):
        """Test serialization of a user without any role."""
        user = CustomUser.objects.create_user(  # type: ignore[call-arg]
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
        user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="client@test.com", password="testpass123", first_name="Client", last_name="Test"
        )
        Client.objects.create(user=user)

        serializer = self.CustomUserSerializer(user)
        data = serializer.data

        self.assertEqual(data["email"], "client@test.com")
        self.assertEqual(data["role"], UserRole.CLIENT.value)

    def test_serialize_social_worker(self):
        """Test serialization of a user with SOCIAL_WORKER role."""
        user = CustomUser.objects.create_user(  # type: ignore[call-arg]
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
        user = CustomUser.objects.create_user(  # type: ignore[call-arg]
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
        user = CustomUser.objects.create_user(  # type: ignore[call-arg]
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
            name="Centre Social Test",
            street_number="123",
            street_name="Rue Test",
            postal_code="75001",
            city="Paris",
            mail="centre@test.com",
        )

        # Create shop
        self.shop = Shop.objects.create(
            name="Magasin Test",
            street_number="456",
            street_name="Avenue Test",
            postal_code="75002",
            city="Paris",
            social_center=self.social_center,
        )

        # Create cashier user
        self.cashier_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="cashier@test.com",
            password="testpass123",
            first_name="Caissier",
            last_name="Test",
        )
        self.cashier = Cashier.objects.create(user=self.cashier_user, shop=self.shop)

        # Create client user
        self.client_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="client@test.com", password="testpass123", first_name="Client", last_name="Test"
        )
        self.test_client_user = Client.objects.create(user=self.client_user)

        # Create other role users for permission testing
        self.social_worker_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="socialworker@test.com",
            password="testpass123",
            first_name="Travailleur",
            last_name="Social",
        )
        SocialWorker.objects.create(user=self.social_worker_user, social_center=self.social_center)

        self.recipient_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
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
            "client_id": self.test_client_user.pk,
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

        assert article is not None
        self.assertEqual(article.client, self.test_client_user)
        self.assertEqual(article.shop, self.shop)
        self.assertIsNone(article.cart)

    def test_create_articles_unauthenticated(self):
        """Test that unauthenticated users cannot create articles."""
        data = {
            "client_id": self.test_client_user.pk,
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
            "client_id": self.test_client_user.pk,
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
            "client_id": self.test_client_user.pk,
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
            "client_id": self.test_client_user.pk,
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
            "client_id": self.test_client_user.pk,
            "articles": articles_list,
        }

        response = self.api_client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Article.objects.count(), MAX_ARTICLES_PER_REQUEST)

    def test_create_articles_invalid_barcode(self):
        """Test that invalid barcode format returns 400 error."""
        self.api_client.force_authenticate(user=self.cashier_user)

        data = {
            "client_id": self.test_client_user.pk,
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
            "client_id": self.test_client_user.pk,
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
            street_number="123",
            street_name="Rue Test",
            postal_code="75001",
            city="Paris",
            mail="centre@test.com",
        )

        # Create shops
        self.shop1 = Shop.objects.create(
            name="Magasin Test 1",
            street_number="456",
            street_name="Avenue Test",
            postal_code="75002",
            city="Paris",
            social_center=self.social_center,
        )
        self.shop2 = Shop.objects.create(
            name="Magasin Test 2",
            street_number="789",
            street_name="Boulevard Test",
            postal_code="75003",
            city="Paris",
            social_center=self.social_center,
        )

        # Create cashier user and cashier for shop1
        self.cashier_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
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
        self.cashier2_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
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
        self.recipient_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
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
        self.recipient2_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
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
        )

        # Create a cart in PENDING status
        self.cart_pending = Cart.objects.create(
            shop=self.shop1,
            recipient=None,
        )

        # Create a cart already COLLECTED
        self.cart_collected = Cart.objects.create(
            shop=self.shop1,
            recipient=self.recipient,
            collected_at=timezone.now(),
        )

        # Create a cart for shop2
        self.cart_shop2 = Cart.objects.create(
            shop=self.shop2,
            recipient=self.recipient,
        )

        # Create client user (for permission tests)
        self.client_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="client@test.com",
            password="testpass123",
            first_name="Client",
            last_name="Test",
        )
        self.test_client_user = Client.objects.create(user=self.client_user)

        self.api_client = APIClient()

    def test_collect_cart_success(self):
        """Test successful cart collection."""
        self.api_client.force_authenticate(user=self.cashier_user)
        url = f"/api/recipients/{self.recipient.user.pk}/carts/{self.cart_assigned.id}/collect/"
        data = {}

        response = self.api_client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

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
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class ClientArticleListViewTests(APITestCase):
    """Test suite for the Client's article list endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        # Create social center
        self.social_center = SocialCenter.objects.create(
            name="Centre Social Test",
            street_number="123",
            street_name="Rue Test",
            postal_code="75001",
            city="Paris",
            mail="centre@test.com",
        )

        # Create shops
        self.shop1 = Shop.objects.create(
            name="Carrefour City Centre",
            street_number="456",
            street_name="Avenue Test",
            postal_code="75002",
            city="Paris",
            social_center=self.social_center,
        )
        self.shop2 = Shop.objects.create(
            name="Monoprix Gare",
            street_number="789",
            street_name="Boulevard Test",
            postal_code="75003",
            city="Paris",
            social_center=self.social_center,
        )

        # Create client user
        self.client_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="client@test.com",
            password="testpass123",
            first_name="Client",
            last_name="Test",
        )
        self.client = Client.objects.create(user=self.client_user)

        # Create another client user for permission tests
        self.client2_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="client2@test.com",
            password="testpass123",
            first_name="Client2",
            last_name="Test",
        )
        self.client2 = Client.objects.create(user=self.client2_user)

        # Create cashier user for permission tests
        self.cashier_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="cashier@test.com",
            password="testpass123",
            first_name="Caissier",
            last_name="Test",
        )
        self.cashier = Cashier.objects.create(user=self.cashier_user, shop=self.shop1)

        # Create recipient user
        self.recipient_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="recipient@test.com",
            password="testpass123",
            first_name="Recipient",
            last_name="Test",
        )
        self.recipient = Recipient.objects.create(
            user=self.recipient_user,
            social_center=self.social_center,
        )

        # Create carts with different statuses
        self.cart_assigned = Cart.objects.create(
            shop=self.shop1,
            recipient=self.recipient,
        )
        self.cart_collected = Cart.objects.create(
            shop=self.shop1,
            recipient=self.recipient,
            collected_at=timezone.now(),
        )

        # Create articles with different statuses
        # Article 1: AVAILABLE (no cart)
        self.article1 = Article.objects.create(
            name="Product 1",
            barcode=3017620422003,
            client=self.client,
            shop=self.shop1,
            cart=None,
        )

        # Article 2: ASSIGNED (cart with ASSIGNED status)
        self.article2 = Article.objects.create(
            name="Product 2",
            barcode=3564700013151,
            client=self.client,
            shop=self.shop1,
            cart=self.cart_assigned,
        )

        # Article 3: COLLECTED (cart with COLLECTED status)
        self.article3 = Article.objects.create(
            name="Product 3",
            barcode=3270190207092,
            client=self.client,
            shop=self.shop2,
            cart=self.cart_collected,
        )

        # Article 4: Another AVAILABLE article
        self.article4 = Article.objects.create(
            name="Product 4",
            barcode=8712566405619,
            client=self.client,
            shop=self.shop1,
            cart=None,
        )

        # Article for client2 (should not be visible to client1)
        self.article_other_client = Article.objects.create(
            name="Other Client Product",
            barcode=5410188031508,
            client=self.client2,
            shop=self.shop1,
            cart=None,
        )

        self.api_client = APIClient()
        self.url = "/api/clients/me/articles/"

    def test_get_articles_success(self):
        """Test successful retrieval of articles for authenticated client."""
        self.api_client.force_authenticate(user=self.client_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("articles", response.data)
        self.assertEqual(response.data["count"], 4)
        self.assertEqual(len(response.data["articles"]), 4)

    def test_get_articles_with_correct_structure(self):
        """Test that articles have the correct structure."""
        self.api_client.force_authenticate(user=self.client_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check first article structure
        article = response.data["articles"][0]
        self.assertIn("id", article)
        self.assertIn("barcode", article)
        self.assertIn("name", article)
        self.assertIn("shop", article)
        self.assertIn("status", article)
        self.assertIn("cart", article)

        # Check shop structure
        self.assertIn("id", article["shop"])
        self.assertIn("name", article["shop"])

    def test_get_articles_status_available(self):
        """Test that articles without cart have AVAILABLE status."""
        self.api_client.force_authenticate(user=self.client_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Find article without cart
        available_articles = [a for a in response.data["articles"] if a["cart"] is None]

        self.assertTrue(len(available_articles) >= 2)
        for article in available_articles:
            self.assertEqual(article["status"], "AVAILABLE")
            self.assertIsNone(article["cart"])

    def test_get_articles_status_assigned(self):
        """Test that articles in ASSIGNED cart have ASSIGNED status."""
        self.api_client.force_authenticate(user=self.client_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Find article with ASSIGNED cart
        assigned_article = next(
            (a for a in response.data["articles"] if a["id"] == self.article2.id), None
        )

        self.assertIsNotNone(assigned_article)
        self.assertEqual(assigned_article["status"], CartStatus.ASSIGNED.value)
        self.assertIsNotNone(assigned_article["cart"])
        self.assertEqual(assigned_article["cart"]["status"], CartStatus.ASSIGNED.value)

    def test_get_articles_status_collected(self):
        """Test that articles in COLLECTED cart have COLLECTED status."""
        self.api_client.force_authenticate(user=self.client_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Find article with COLLECTED cart
        collected_article = next(
            (a for a in response.data["articles"] if a["id"] == self.article3.id), None
        )

        self.assertIsNotNone(collected_article)
        self.assertEqual(collected_article["status"], CartStatus.COLLECTED.value)
        self.assertIsNotNone(collected_article["cart"])
        self.assertEqual(collected_article["cart"]["status"], CartStatus.COLLECTED.value)

    def test_get_articles_ordered_by_most_recent(self):
        """Test that articles are ordered by most recent first."""
        self.api_client.force_authenticate(user=self.client_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that IDs are in descending order (most recent first)
        article_ids = [a["id"] for a in response.data["articles"]]
        self.assertEqual(article_ids, sorted(article_ids, reverse=True))

    def test_get_articles_only_own_articles(self):
        """Test that clients can only see their own articles."""
        self.api_client.force_authenticate(user=self.client_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify that article from client2 is not in the response
        article_ids = [a["id"] for a in response.data["articles"]]
        self.assertNotIn(self.article_other_client.id, article_ids)

        # Verify all articles belong to client1
        self.assertEqual(response.data["count"], 4)

    def test_get_articles_empty_list(self):
        """Test that clients with no articles get empty list."""
        # Create a new client without articles
        new_client_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="newclient@test.com",
            password="testpass123",
            first_name="New",
            last_name="Client",
        )
        Client.objects.create(user=new_client_user)

        self.api_client.force_authenticate(user=new_client_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["articles"]), 0)

    def test_get_articles_unauthenticated(self):
        """Test that unauthenticated users cannot access articles."""
        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_articles_non_client_user(self):
        """Test that non-client users cannot access the endpoint."""
        # Test with cashier
        self.api_client.force_authenticate(user=self.cashier_user)
        response = self.api_client.get(self.url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Test with recipient
        self.api_client.force_authenticate(user=self.recipient_user)
        response = self.api_client.get(self.url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_articles_shop_information(self):
        """Test that shop information is correctly included."""
        self.api_client.force_authenticate(user=self.client_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Find article from shop1
        shop1_article = next(
            (a for a in response.data["articles"] if a["id"] == self.article1.id), None
        )

        self.assertIsNotNone(shop1_article)
        self.assertEqual(shop1_article["shop"]["id"], self.shop1.id)
        self.assertEqual(shop1_article["shop"]["name"], "Carrefour City Centre")

        # Find article from shop2
        shop2_article = next(
            (a for a in response.data["articles"] if a["id"] == self.article3.id), None
        )

        self.assertIsNotNone(shop2_article)
        self.assertEqual(shop2_article["shop"]["id"], self.shop2.id)
        self.assertEqual(shop2_article["shop"]["name"], "Monoprix Gare")


class RecipientCartListViewTests(APITestCase):
    """Test suite for the RecipientCartListView endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        # Create social center
        self.social_center = SocialCenter.objects.create(
            name="Centre Social Test",
            street_number="123",
            street_name="Rue Test",
            postal_code="75001",
            city="Paris",
            mail="centre@test.com",
        )

        # Create shops
        self.shop1 = Shop.objects.create(
            name="Carrefour City Centre",
            street_number="456",
            street_name="Avenue Test",
            postal_code="75002",
            city="Paris",
            social_center=self.social_center,
        )
        self.shop2 = Shop.objects.create(
            name="Monoprix Gare",
            street_number="789",
            street_name="Boulevard Test",
            postal_code="75003",
            city="Paris",
            social_center=self.social_center,
        )

        # Create recipient user
        self.recipient_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="recipient@test.com",
            password="testpass123",
            first_name="Bénéficiaire",
            last_name="Test",
        )
        self.recipient = Recipient.objects.create(
            user=self.recipient_user,
            social_center=self.social_center,
        )

        # Create another recipient for isolation tests
        self.recipient2_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="recipient2@test.com",
            password="testpass123",
            first_name="Bénéficiaire2",
            last_name="Test",
        )
        self.recipient2 = Recipient.objects.create(
            user=self.recipient2_user,
            social_center=self.social_center,
        )

        # Create client user for permission tests
        self.client_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="client@test.com",
            password="testpass123",
            first_name="Client",
            last_name="Test",
        )
        self.client = Client.objects.create(user=self.client_user)

        # Create cashier user for permission tests
        self.cashier_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="cashier@test.com",
            password="testpass123",
            first_name="Caissier",
            last_name="Test",
        )
        self.cashier = Cashier.objects.create(user=self.cashier_user, shop=self.shop1)

        # Create carts with different statuses for recipient1
        # Note: PENDING carts have no recipient, so they won't appear in recipient cart lists

        self.cart_assigned1 = Cart.objects.create(
            shop=self.shop1,
            recipient=self.recipient,  # ASSIGNED: has recipient, no collected_at
        )

        self.cart_assigned2 = Cart.objects.create(
            shop=self.shop2,
            recipient=self.recipient,  # ASSIGNED: has recipient, no collected_at
        )

        self.cart_collected = Cart.objects.create(
            shop=self.shop1,
            recipient=self.recipient,
            collected_at=timezone.now(),  # COLLECTED: has recipient and collected_at
        )

        # Create cart for recipient2 (should not be visible to recipient1)
        self.cart_other_recipient = Cart.objects.create(
            shop=self.shop1,
            recipient=self.recipient2,  # ASSIGNED: has recipient, no collected_at
        )

        # Create articles for carts
        self.article1 = Article.objects.create(
            name="Product 1",
            barcode=3017620422003,
            client=self.client,
            shop=self.shop1,
            cart=self.cart_assigned1,
        )

        self.article2 = Article.objects.create(
            name="Product 2",
            barcode=3564700013151,
            client=self.client,
            shop=self.shop1,
            cart=self.cart_assigned1,
        )

        self.article3 = Article.objects.create(
            name="Product 3",
            barcode=3270190207092,
            client=self.client,
            shop=self.shop2,
            cart=self.cart_assigned2,
        )

        self.article4 = Article.objects.create(
            name="Product 4",
            barcode=8712566405619,
            client=self.client,
            shop=self.shop1,
            cart=self.cart_collected,
        )

        self.api_client = APIClient()
        self.url = "/api/recipients/me/carts/"

    def test_get_carts_success(self):
        """Test successful retrieval of carts for authenticated recipient."""
        self.api_client.force_authenticate(user=self.recipient_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 3)  # 2 ASSIGNED + 1 COLLECTED
        self.assertEqual(len(response.data["results"]), 3)

    def test_get_carts_with_correct_structure(self):
        """Test that carts have the correct structure with nested articles."""
        self.api_client.force_authenticate(user=self.recipient_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check first cart structure
        cart = response.data["results"][0]
        self.assertIn("id", cart)
        self.assertIn("shop", cart)
        self.assertIn("shop_name", cart)
        self.assertIn("recipient", cart)
        self.assertIn("recipient_email", cart)
        self.assertIn("recipient_name", cart)
        self.assertIn("status", cart)
        self.assertIn("collected_at", cart)
        self.assertIn("articles", cart)

        # Check articles structure
        self.assertIsInstance(cart["articles"], list)
        if len(cart["articles"]) > 0:
            article = cart["articles"][0]
            self.assertIn("id", article)
            self.assertIn("barcode", article)
            self.assertIn("name", article)

    def test_get_carts_includes_articles(self):
        """Test that carts include their associated articles."""
        self.api_client.force_authenticate(user=self.recipient_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Find cart_assigned1 which has 2 articles
        cart_with_articles = next(
            (c for c in response.data["results"] if c["id"] == self.cart_assigned1.id), None
        )

        self.assertIsNotNone(cart_with_articles)
        self.assertEqual(len(cart_with_articles["articles"]), 2)

        # Verify article IDs
        article_ids = [a["id"] for a in cart_with_articles["articles"]]
        self.assertIn(self.article1.id, article_ids)
        self.assertIn(self.article2.id, article_ids)

    def test_get_carts_ordered_by_most_recent(self):
        """Test that carts are ordered by most recent first (descending ID)."""
        self.api_client.force_authenticate(user=self.recipient_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that IDs are in descending order (most recent first)
        cart_ids = [c["id"] for c in response.data["results"]]
        self.assertEqual(cart_ids, sorted(cart_ids, reverse=True))

    def test_get_carts_only_own_carts(self):
        """Test that recipients can only see their own carts."""
        self.api_client.force_authenticate(user=self.recipient_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify that cart from recipient2 is not in the response
        cart_ids = [c["id"] for c in response.data["results"]]
        self.assertNotIn(self.cart_other_recipient.id, cart_ids)

        # Verify all carts belong to recipient1 (2 ASSIGNED + 1 COLLECTED)
        self.assertEqual(response.data["count"], 3)

    def test_get_carts_filter_by_status_assigned(self):
        """Test filtering carts by ASSIGNED status."""
        self.api_client.force_authenticate(user=self.recipient_user)

        response = self.api_client.get(self.url, {"status": "ASSIGNED"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

        # Verify all returned carts have ASSIGNED status
        for cart in response.data["results"]:
            self.assertEqual(cart["status"], CartStatus.ASSIGNED.value)

    def test_get_carts_filter_by_status_pending(self):
        """Test filtering carts by PENDING status returns empty list."""
        self.api_client.force_authenticate(user=self.recipient_user)

        response = self.api_client.get(self.url, {"status": "PENDING"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # PENDING carts have no recipient, so filtering by PENDING should return 0 carts
        self.assertEqual(response.data["count"], 0)

    def test_get_carts_filter_by_status_collected(self):
        """Test filtering carts by COLLECTED status."""
        self.api_client.force_authenticate(user=self.recipient_user)

        response = self.api_client.get(self.url, {"status": "COLLECTED"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["status"], CartStatus.COLLECTED.value)

    def test_get_carts_filter_invalid_status(self):
        """Test filtering with invalid status returns 400."""
        self.api_client.force_authenticate(user=self.recipient_user)

        response = self.api_client.get(self.url, {"status": "INVALID_STATUS"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_get_carts_pagination(self):
        """Test pagination of cart results."""
        self.api_client.force_authenticate(user=self.recipient_user)

        # Create more carts to test pagination (total should be > 20 for default page size)
        # We already have 3, create 18 more to have 21 total
        for _ in range(18):
            Cart.objects.create(
                shop=self.shop1,
                recipient=self.recipient,  # ASSIGNED: has recipient, no collected_at
            )

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 21)
        self.assertEqual(len(response.data["results"]), 20)  # Page size is 20
        self.assertIsNotNone(response.data["next"])
        self.assertIsNone(response.data["previous"])

    def test_get_carts_pagination_page_2(self):
        """Test accessing page 2 of paginated results."""
        self.api_client.force_authenticate(user=self.recipient_user)

        # Create more carts to test pagination
        for _ in range(18):
            Cart.objects.create(
                shop=self.shop1,
                recipient=self.recipient,  # ASSIGNED: has recipient, no collected_at
            )

        response = self.api_client.get(self.url, {"page": 2}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 21)
        self.assertEqual(len(response.data["results"]), 1)  # Only 1 cart on page 2
        self.assertIsNone(response.data["next"])
        self.assertIsNotNone(response.data["previous"])

    def test_get_carts_pagination_with_filter(self):
        """Test pagination combined with status filtering."""
        self.api_client.force_authenticate(user=self.recipient_user)

        # Create more ASSIGNED carts (we already have 2, need 19 more for 21 total)
        for _ in range(19):
            Cart.objects.create(
                shop=self.shop1,
                recipient=self.recipient,  # ASSIGNED: has recipient, no collected_at
            )

        response = self.api_client.get(self.url, {"status": "ASSIGNED"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 21)  # 2 original + 19 new = 21
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])

    def test_get_carts_empty_list(self):
        """Test that recipients with no carts get empty list."""
        # Create a new recipient without carts
        new_recipient_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="newrecipient@test.com",
            password="testpass123",
            first_name="New",
            last_name="Recipient",
        )
        Recipient.objects.create(user=new_recipient_user, social_center=self.social_center)

        self.api_client.force_authenticate(user=new_recipient_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["results"]), 0)

    def test_get_carts_unauthenticated(self):
        """Test that unauthenticated users cannot access carts."""
        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_carts_non_recipient_user(self):
        """Test that non-recipient users cannot access the endpoint."""
        # Test with client
        self.api_client.force_authenticate(user=self.client_user)
        response = self.api_client.get(self.url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Test with cashier
        self.api_client.force_authenticate(user=self.cashier_user)
        response = self.api_client.get(self.url, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_carts_shop_information(self):
        """Test that shop information is correctly included."""
        self.api_client.force_authenticate(user=self.recipient_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Find cart from shop1
        shop1_cart = next(
            (c for c in response.data["results"] if c["id"] == self.cart_assigned1.id), None
        )

        self.assertIsNotNone(shop1_cart)
        self.assertEqual(shop1_cart["shop"], self.shop1.id)
        self.assertEqual(shop1_cart["shop_name"], "Carrefour City Centre")

        # Find cart from shop2
        shop2_cart = next(
            (c for c in response.data["results"] if c["id"] == self.cart_assigned2.id), None
        )

        self.assertIsNotNone(shop2_cart)
        self.assertEqual(shop2_cart["shop"], self.shop2.id)
        self.assertEqual(shop2_cart["shop_name"], "Monoprix Gare")

    def test_get_carts_recipient_information(self):
        """Test that recipient information is correctly included."""
        self.api_client.force_authenticate(user=self.recipient_user)

        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        cart = response.data["results"][0]
        self.assertEqual(cart["recipient"], self.recipient.user.pk)
        self.assertEqual(cart["recipient_email"], "recipient@test.com")
        self.assertEqual(cart["recipient_name"], "Bénéficiaire Test")


class CartDetailViewTests(APITestCase):
    """Tests for the CartDetailView endpoint."""

    def setUp(self):
        """Set up test data."""
        # Create social center
        self.social_center = SocialCenter.objects.create(
            name="Test Social Center",
            mail="centre@test.com",
        )

        # Create shops
        self.shop1 = Shop.objects.create(
            name="Shop 1",
            social_center=self.social_center,
        )
        self.shop2 = Shop.objects.create(
            name="Shop 2",
            social_center=self.social_center,
        )

        # Create cashier user for shop1
        self.cashier_user = CustomUser.objects.create_user(
            email="cashier@example.com",
            password="testpass123",
        )
        self.cashier = Cashier.objects.create(user=self.cashier_user, shop=self.shop1)

        # Create another cashier for shop2
        self.cashier2_user = CustomUser.objects.create_user(
            email="cashier2@example.com",
            password="testpass123",
        )
        self.cashier2 = Cashier.objects.create(user=self.cashier2_user, shop=self.shop2)

        # Create recipient
        self.recipient_user = CustomUser.objects.create_user(
            email="recipient@example.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
        )
        self.recipient = Recipient.objects.create(
            user=self.recipient_user,
            social_center=self.social_center,
        )

        # Create client
        self.client_user = CustomUser.objects.create_user(
            email="client@example.com",
            password="testpass123",
        )
        self.client = Client.objects.create(user=self.client_user)

        # Create social worker
        self.social_worker_user = CustomUser.objects.create_user(
            email="socialworker@example.com",
            password="testpass123",
        )
        self.social_worker = SocialWorker.objects.create(
            user=self.social_worker_user,
            social_center=self.social_center,
        )

        # Create carts
        self.cart_pending = Cart.objects.create(shop=self.shop1)
        self.cart_assigned = Cart.objects.create(shop=self.shop1, recipient=self.recipient)
        self.cart_collected = Cart.objects.create(
            shop=self.shop1,
            recipient=self.recipient,
            collected_at=timezone.now(),
        )
        self.cart_shop2 = Cart.objects.create(shop=self.shop2, recipient=self.recipient)

        # Create articles for cart_assigned
        self.article1 = Article.objects.create(
            barcode="3017620422003",
            name="Product 1",
            shop=self.shop1,
            client=self.client,
            cart=self.cart_assigned,
        )
        self.article2 = Article.objects.create(
            barcode="3564700013151",
            name="Product 2",
            shop=self.shop1,
            client=self.client,
            cart=self.cart_assigned,
        )

        self.api_client = APIClient()

    def test_get_cart_success(self):
        """Test successful cart retrieval."""
        self.api_client.force_authenticate(user=self.cashier_user)
        url = f"/api/carts/{self.cart_assigned.id}/"

        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.cart_assigned.id)
        self.assertEqual(response.data["shop"], self.shop1.id)
        self.assertEqual(response.data["shop_name"], "Shop 1")
        self.assertEqual(response.data["recipient"], self.recipient.user.id)
        self.assertEqual(response.data["recipient_email"], "recipient@example.com")
        self.assertEqual(response.data["recipient_name"], "John Doe")
        self.assertEqual(response.data["status"], "ASSIGNED")
        self.assertIsNone(response.data["collected_at"])
        self.assertEqual(len(response.data["articles"]), 2)
        self.assertEqual(response.data["articles"][0]["name"], "Product 1")
        self.assertEqual(response.data["articles"][1]["name"], "Product 2")

    def test_get_cart_pending_status(self):
        """Test retrieving a pending cart."""
        self.api_client.force_authenticate(user=self.cashier_user)
        url = f"/api/carts/{self.cart_pending.id}/"

        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "PENDING")
        self.assertIsNone(response.data["recipient"])
        self.assertEqual(len(response.data["articles"]), 0)

    def test_get_cart_collected_status(self):
        """Test retrieving a collected cart."""
        self.api_client.force_authenticate(user=self.cashier_user)
        url = f"/api/carts/{self.cart_collected.id}/"

        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "COLLECTED")
        self.assertIsNotNone(response.data["collected_at"])

    def test_get_cart_not_found(self):
        """Test retrieving a non-existent cart returns 404."""
        self.api_client.force_authenticate(user=self.cashier_user)
        url = "/api/carts/99999/"

        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"], "Cart not found.")

    def test_get_cart_wrong_shop(self):
        """Test retrieving a cart from another shop returns 403."""
        self.api_client.force_authenticate(user=self.cashier_user)
        url = f"/api/carts/{self.cart_shop2.id}/"

        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["error"], "You can only access carts from your shop.")

    def test_get_cart_unauthenticated(self):
        """Test unauthenticated request returns 401."""
        url = f"/api/carts/{self.cart_assigned.id}/"

        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_cart_wrong_role_client(self):
        """Test client role cannot access endpoint."""
        self.api_client.force_authenticate(user=self.client_user)
        url = f"/api/carts/{self.cart_assigned.id}/"

        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_cart_wrong_role_recipient(self):
        """Test recipient role cannot access endpoint."""
        self.api_client.force_authenticate(user=self.recipient_user)
        url = f"/api/carts/{self.cart_assigned.id}/"

        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_cart_wrong_role_social_worker(self):
        """Test social worker role cannot access endpoint."""
        self.api_client.force_authenticate(user=self.social_worker_user)
        url = f"/api/carts/{self.cart_assigned.id}/"

        response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from api.constants import MAX_ARTICLES_PER_REQUEST
from api.enums import CartStatus
from api.models import (
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

        # Verify new fields exist in response
        for article_data in response.data["articles"]:
            self.assertIn("img_url", article_data)
            self.assertIn("thumb_url", article_data)
            self.assertIn("brand_label", article_data)
            self.assertIn("created_at", article_data)
            self.assertIn("updated_at", article_data)

        # Verify timestamps are automatically generated
        self.assertIsNotNone(article.created_at)
        self.assertIsNotNone(article.updated_at)

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
        articles_list = [{"barcode": 3017620422003 + i} for i in range(MAX_ARTICLES_PER_REQUEST + 1)]

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

    def test_create_articles_with_optional_fields(self):
        """Test successful article creation with optional fields (name, img_url, thumb_url, brand_label)."""
        self.api_client.force_authenticate(user=self.cashier_user)

        data = {
            "client_id": self.test_client_user.pk,
            "articles": [
                {
                    "barcode": 3017620422003,
                    "name": "Coca-Cola 33cl",
                    "img_url": "https://example.com/image1.jpg",
                    "thumb_url": "https://example.com/thumb1.jpg",
                    "brand_label": "Coca-Cola",
                },
                {
                    "barcode": 3564700013151,
                    "name": "KitKat",
                    "brand_label": "Nestle",
                },
                {
                    "barcode": 3270190207092,
                },
            ],
        }

        response = self.api_client.post(self.url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Article.objects.count(), 3)

        # Verify first article with all optional fields
        article1 = Article.objects.get(barcode=3017620422003)
        self.assertEqual(article1.name, "Coca-Cola 33cl")
        self.assertEqual(article1.img_url, "https://example.com/image1.jpg")
        self.assertEqual(article1.thumb_url, "https://example.com/thumb1.jpg")
        self.assertEqual(article1.brand_label, "Coca-Cola")

        # Verify second article with partial optional fields
        article2 = Article.objects.get(barcode=3564700013151)
        self.assertEqual(article2.name, "KitKat")
        self.assertEqual(article2.img_url, "")
        self.assertEqual(article2.thumb_url, "")
        self.assertEqual(article2.brand_label, "Nestle")

        # Verify third article without optional fields
        article3 = Article.objects.get(barcode=3270190207092)
        self.assertEqual(article3.name, "")
        self.assertEqual(article3.img_url, "")
        self.assertEqual(article3.thumb_url, "")
        self.assertEqual(article3.brand_label, "")


class ArticleGetListViewTests(APITestCase):
    """Tests for the ArticleGetListView endpoint (GET /clients/me/articles/)."""

    def setUp(self):
        """Set up test data for article list tests."""
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

        # Create client user
        self.client_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="client@test.com", password="testpass123", first_name="Client", last_name="Test"
        )
        self.test_client = Client.objects.create(user=self.client_user)

        # Create another client user for testing isolation
        self.other_client_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="otherclient@test.com",
            password="testpass123",
            first_name="Other",
            last_name="Client",
        )
        self.other_client = Client.objects.create(user=self.other_client_user)

        # Create other role users for permission testing
        self.cashier_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="cashier@test.com",
            password="testpass123",
            first_name="Caissier",
            last_name="Test",
        )
        Cashier.objects.create(user=self.cashier_user, shop=self.shop)

        self.social_worker_user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="socialworker@test.com",
            password="testpass123",
            first_name="Travailleur",
            last_name="Social",
        )
        SocialWorker.objects.create(user=self.social_worker_user, social_center=self.social_center)

        # Create cart for testing article status
        self.cart = Cart.objects.create(shop=self.shop)

        # API client
        self.api_client = APIClient()
        self.url = "/api/clients/me/articles/"

    def test_get_articles_list_success(self):
        """Test successful retrieval of client's articles."""
        self.api_client.force_authenticate(user=self.client_user)

        # Create articles for the client with various states
        article1 = Article.objects.create(
            name="Article 1",
            barcode=3017620422003,
            client=self.test_client,
            shop=self.shop,
            img_url="https://example.com/img1.jpg",
            thumb_url="https://example.com/thumb1.jpg",
            brand_label="Brand A",
        )
        article2 = Article.objects.create(
            name="Article 2",
            barcode=3564700013151,
            client=self.test_client,
            shop=self.shop,
            cart=self.cart,
            brand_label="Brand B",
        )
        article3 = Article.objects.create(
            name="Article 3",
            barcode=3270190207092,
            client=self.test_client,
            shop=self.shop,
        )

        response = self.api_client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("articles", response.data)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["articles"]), 3)

        # Verify all new fields are present in response
        for article_data in response.data["articles"]:
            self.assertIn("id", article_data)
            self.assertIn("barcode", article_data)
            self.assertIn("name", article_data)
            self.assertIn("img_url", article_data)
            self.assertIn("thumb_url", article_data)
            self.assertIn("brand_label", article_data)
            self.assertIn("shop", article_data)
            self.assertIn("status", article_data)
            self.assertIn("cart", article_data)
            self.assertIn("created_at", article_data)
            self.assertIn("updated_at", article_data)

        # Verify specific values for first article
        article1_data = next(a for a in response.data["articles"] if a["id"] == article1.id)
        self.assertEqual(article1_data["img_url"], "https://example.com/img1.jpg")
        self.assertEqual(article1_data["thumb_url"], "https://example.com/thumb1.jpg")
        self.assertEqual(article1_data["brand_label"], "Brand A")
        self.assertEqual(article1_data["status"], "AVAILABLE")
        self.assertIsNone(article1_data["cart"])

        # Verify article with cart assigned
        article2_data = next(a for a in response.data["articles"] if a["id"] == article2.id)
        self.assertEqual(article2_data["brand_label"], "Brand B")
        self.assertEqual(article2_data["status"], "PENDING")
        self.assertIsNotNone(article2_data["cart"])

        # Verify article without optional fields
        article3_data = next(a for a in response.data["articles"] if a["id"] == article3.id)
        self.assertEqual(article3_data["img_url"], "")
        self.assertEqual(article3_data["thumb_url"], "")
        self.assertEqual(article3_data["brand_label"], "")

    def test_get_articles_list_unauthenticated(self):
        """Test that unauthenticated users cannot access articles list."""
        response = self.api_client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_articles_list_non_client_user(self):
        """Test that non-client users (cashier, social worker) cannot access articles list."""
        # Test with cashier
        self.api_client.force_authenticate(user=self.cashier_user)
        response = self.api_client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Test with social worker
        self.api_client.force_authenticate(user=self.social_worker_user)
        response = self.api_client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_articles_list_only_own_articles(self):
        """Test that clients only see their own articles."""
        self.api_client.force_authenticate(user=self.client_user)

        # Create articles for both clients
        Article.objects.create(
            name="My Article",
            barcode=3017620422003,
            client=self.test_client,
            shop=self.shop,
        )
        Article.objects.create(
            name="Other Article",
            barcode=3564700013151,
            client=self.other_client,
            shop=self.shop,
        )

        response = self.api_client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["articles"][0]["name"], "My Article")

    def test_get_articles_list_empty(self):
        """Test that clients with no articles get an empty list."""
        self.api_client.force_authenticate(user=self.client_user)

        response = self.api_client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["articles"]), 0)


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
        assigned_article = next((a for a in response.data["articles"] if a["id"] == self.article2.id), None)

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
        collected_article = next((a for a in response.data["articles"] if a["id"] == self.article3.id), None)

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
        shop1_article = next((a for a in response.data["articles"] if a["id"] == self.article1.id), None)

        self.assertIsNotNone(shop1_article)
        self.assertEqual(shop1_article["shop"]["id"], self.shop1.id)
        self.assertEqual(shop1_article["shop"]["name"], "Carrefour City Centre")

        # Find article from shop2
        shop2_article = next((a for a in response.data["articles"] if a["id"] == self.article3.id), None)

        self.assertIsNotNone(shop2_article)
        self.assertEqual(shop2_article["shop"]["id"], self.shop2.id)
        self.assertEqual(shop2_article["shop"]["name"], "Monoprix Gare")


class ArticleBarcodeViewTests(APITestCase):
    """Tests for GET /api/articles/barcode/<barcode>/."""

    BARCODE = 3017620422003
    URL = f"/api/articles/barcode/{BARCODE}/"

    def setUp(self) -> None:
        """Create shared fixtures: social center, shop, client user, and one article."""
        self.social_center = SocialCenter.objects.create(
            name="Centre Barcode Test",
            street_number="1",
            street_name="Rue Test",
            postal_code="75001",
            city="Paris",
            mail="barcode@test.com",
        )
        self.shop = Shop.objects.create(
            name="Magasin Barcode Test",
            street_number="2",
            street_name="Avenue Test",
            postal_code="75002",
            city="Paris",
            social_center=self.social_center,
        )
        self.client_user = CustomUser.objects.create_user(  # type: ignore[attr-defined]
            email="barcode_client@test.com",
            password="SecurePass123!",
            first_name="Client",
            last_name="Barcode",
        )
        self.client_obj = Client.objects.create(user=self.client_user)
        self.cashier_user = CustomUser.objects.create_user(  # type: ignore[attr-defined]
            email="barcode_cashier@test.com",
            password="SecurePass123!",
            first_name="Cashier",
            last_name="Barcode",
        )
        Cashier.objects.create(user=self.cashier_user, shop=self.shop)
        self.article = Article.objects.create(
            name="Nutella 400g",
            barcode=self.BARCODE,
            client=self.client_obj,
            shop=self.shop,
            img_url="https://cdn.example.com/nutella.jpg",
            brand_label="Ferrero",
        )

    def test_returns_article_when_barcode_exists(self) -> None:
        """200 response with article data for a known barcode."""
        self.client.force_authenticate(user=self.client_user)
        response = self.client.get(self.URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["barcode"], self.BARCODE)
        self.assertEqual(response.data["name"], "Nutella 400g")
        self.assertEqual(response.data["brand_label"], "Ferrero")

    def test_returns_404_when_barcode_does_not_exist(self) -> None:
        """404 when no article matches the given barcode."""
        self.client.force_authenticate(user=self.client_user)
        response = self.client.get("/api/articles/barcode/9999999999999/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("detail", response.data)

    def test_unauthenticated_returns_401(self) -> None:
        """401 when the request has no authentication credentials."""
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cashier_returns_403(self) -> None:
        """403 when a Cashier (non-client) tries to access the endpoint."""
        self.client.force_authenticate(user=self.cashier_user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_first_article_when_multiple_share_barcode(self) -> None:
        """The endpoint returns the first (oldest) article for a duplicated barcode."""
        client_user2 = CustomUser.objects.create_user(  # type: ignore[attr-defined]
            email="barcode_client2@test.com",
            password="SecurePass123!",
            first_name="Client2",
            last_name="Barcode",
        )
        client_obj2 = Client.objects.create(user=client_user2)
        Article.objects.create(
            name="Nutella 400g (copy)",
            barcode=self.BARCODE,
            client=client_obj2,
            shop=self.shop,
        )
        self.client.force_authenticate(user=self.client_user)
        response = self.client.get(self.URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.article.pk)

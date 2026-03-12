from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from api.models import (
    Shop,
    SocialCenter,
)


class ShopDetailViewTests(APITestCase):
    """Tests for the ShopDetailView endpoint."""

    def setUp(self):
        """Set up test data for shop detail tests."""
        # Create social center
        self.social_center = SocialCenter.objects.create(
            name="Centre Social Test",
            street_number="10",
            street_name="Rue du Centre",
            postal_code="75001",
            city="Paris",
            mail="centre@test.com",
        )

        # Create shop with location
        from django.contrib.gis.geos import Point

        self.shop = Shop.objects.create(
            name="Carrefour City Centre",
            street_number="123",
            street_name="Rue de la République",
            postal_code="75001",
            city="Paris",
            social_center=self.social_center,
            location=Point(2.3522, 48.8566, srid=4326),  # longitude, latitude
        )

        self.api_client = APIClient()

    def test_get_shop_detail_success(self):
        """Test successful retrieval of shop details."""
        url = f"/api/shops/{self.shop.id}/"
        response = self.api_client.get(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.shop.id)
        self.assertEqual(response.data["name"], "Carrefour City Centre")
        self.assertEqual(response.data["street_number"], "123")
        self.assertEqual(response.data["street_name"], "Rue de la République")
        self.assertEqual(response.data["postal_code"], "75001")
        self.assertEqual(response.data["city"], "Paris")
        self.assertEqual(response.data["social_center"], self.social_center.id)
        self.assertAlmostEqual(response.data["latitude"], 48.8566, places=4)
        self.assertAlmostEqual(response.data["longitude"], 2.3522, places=4)
        self.assertEqual(response.data["full_address"], "123 Rue de la République, 75001 Paris")

    def test_get_shop_detail_not_found(self):
        """Test that 404 is returned for non-existent shop."""
        url = "/api/shops/9999/"
        response = self.api_client.get(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"], "Shop not found.")

    def test_get_shop_detail_no_authentication_required(self):
        """Test that shop details can be accessed without authentication."""
        url = f"/api/shops/{self.shop.id}/"
        response = self.api_client.get(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_shop_detail_without_location(self):
        """Test shop detail for shop without geographic location."""
        shop_without_location = Shop.objects.create(
            name="Shop Sans Coordonnées",
            street_number="99",
            street_name="Rue Test",
            postal_code="75010",
            city="Paris",
            social_center=self.social_center,
        )

        url = f"/api/shops/{shop_without_location.id}/"
        response = self.api_client.get(url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Shop Sans Coordonnées")
        self.assertIsNone(response.data["latitude"])
        self.assertIsNone(response.data["longitude"])


class ShopListViewTests(APITestCase):
    """Tests for the ShopListView endpoint."""

    def setUp(self):
        """Set up test data for shop list tests."""
        from django.contrib.gis.geos import Point

        # Create social center
        self.social_center = SocialCenter.objects.create(
            name="Centre Social Test",
            street_number="10",
            street_name="Rue du Centre",
            postal_code="75001",
            city="Paris",
            mail="centre@test.com",
        )

        # Create multiple shops with locations
        # Shop 1 - Paris centre (reference point)
        self.shop1 = Shop.objects.create(
            name="Shop Paris Centre",
            street_number="1",
            street_name="Rue de Rivoli",
            postal_code="75001",
            city="Paris",
            social_center=self.social_center,
            location=Point(2.3522, 48.8566, srid=4326),  # Paris centre
        )

        # Shop 2 - Paris nord (closer to test point)
        self.shop2 = Shop.objects.create(
            name="Shop Paris Nord",
            street_number="2",
            street_name="Avenue de Flandre",
            postal_code="75019",
            city="Paris",
            social_center=self.social_center,
            location=Point(2.3700, 48.8900, srid=4326),  # Paris nord
        )

        # Shop 3 - Paris sud (farther from test point)
        self.shop3 = Shop.objects.create(
            name="Shop Paris Sud",
            street_number="3",
            street_name="Avenue d'Italie",
            postal_code="75013",
            city="Paris",
            social_center=self.social_center,
            location=Point(2.3583, 48.8217, srid=4326),  # Paris sud
        )

        # Shop 4 - Without location
        self.shop4 = Shop.objects.create(
            name="Shop Sans Localisation",
            street_number="4",
            street_name="Rue Test",
            postal_code="75010",
            city="Paris",
            social_center=self.social_center,
        )

        self.api_client = APIClient()
        self.url = "/api/shops/"

    def test_list_shops_success(self):
        """Test successful retrieval of shops list."""
        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 4)
        self.assertEqual(len(response.data["results"]), 4)

    def test_list_shops_no_authentication_required(self):
        """Test that shops list can be accessed without authentication."""
        response = self.api_client.get(self.url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_shops_ordered_by_id_default(self):
        """Test that shops are ordered by ID by default (without coordinates)."""
        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]

        # Should be ordered by ID
        self.assertEqual(results[0]["id"], self.shop1.id)
        self.assertEqual(results[1]["id"], self.shop2.id)
        self.assertEqual(results[2]["id"], self.shop3.id)
        self.assertEqual(results[3]["id"], self.shop4.id)

    def test_list_shops_with_proximity_sorting(self):
        """Test shops sorted by proximity to given GPS coordinates."""
        # Test point: Paris nord area (48.8900, 2.3700) - close to shop2
        response = self.api_client.get(self.url, {"latitude": "48.8900", "longitude": "2.3700"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]

        # Shop 2 (Paris Nord) should be first (closest to test point)
        self.assertEqual(results[0]["name"], "Shop Paris Nord")

        # Shop 1 (Paris Centre) should be second
        self.assertEqual(results[1]["name"], "Shop Paris Centre")

        # Shop 3 (Paris Sud) should be third (farthest from test point)
        self.assertEqual(results[2]["name"], "Shop Paris Sud")

        # Shop without location should be last
        self.assertEqual(results[3]["name"], "Shop Sans Localisation")

    def test_list_shops_proximity_sorting_different_point(self):
        """Test proximity sorting with different reference point."""
        # Test point: Paris sud area (48.8217, 2.3583) - close to shop3
        response = self.api_client.get(self.url, {"latitude": "48.8217", "longitude": "2.3583"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]

        # Shop 3 (Paris Sud) should be first (closest to test point)
        self.assertEqual(results[0]["name"], "Shop Paris Sud")

    def test_list_shops_missing_latitude(self):
        """Test that error is returned when only longitude is provided."""
        response = self.api_client.get(self.url, {"longitude": "2.3522"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("coordinates", response.data)
        self.assertEqual(
            response.data["coordinates"],
            "Both latitude and longitude must be provided for proximity sorting.",
        )

    def test_list_shops_missing_longitude(self):
        """Test that error is returned when only latitude is provided."""
        response = self.api_client.get(self.url, {"latitude": "48.8566"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("coordinates", response.data)
        self.assertEqual(
            response.data["coordinates"],
            "Both latitude and longitude must be provided for proximity sorting.",
        )

    def test_list_shops_invalid_latitude_format(self):
        """Test that error is returned for invalid latitude format."""
        response = self.api_client.get(self.url, {"latitude": "invalid", "longitude": "2.3522"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("coordinates", response.data)
        self.assertEqual(response.data["coordinates"], "Invalid coordinate values. Must be valid numbers.")

    def test_list_shops_invalid_longitude_format(self):
        """Test that error is returned for invalid longitude format."""
        response = self.api_client.get(self.url, {"latitude": "48.8566", "longitude": "invalid"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("coordinates", response.data)

    def test_list_shops_latitude_out_of_range(self):
        """Test that error is returned for latitude outside valid range."""
        # Test latitude > 90
        response = self.api_client.get(self.url, {"latitude": "95.0", "longitude": "2.3522"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("latitude", response.data)
        self.assertEqual(response.data["latitude"], "Latitude must be between -90 and 90 degrees.")

        # Test latitude < -90
        response = self.api_client.get(self.url, {"latitude": "-95.0", "longitude": "2.3522"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("latitude", response.data)

    def test_list_shops_longitude_out_of_range(self):
        """Test that error is returned for longitude outside valid range."""
        # Test longitude > 180
        response = self.api_client.get(self.url, {"latitude": "48.8566", "longitude": "185.0"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("longitude", response.data)
        self.assertEqual(response.data["longitude"], "Longitude must be between -180 and 180 degrees.")

        # Test longitude < -180
        response = self.api_client.get(self.url, {"latitude": "48.8566", "longitude": "-185.0"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("longitude", response.data)

    def test_list_shops_pagination(self):
        """Test pagination of shops list."""
        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)

    def test_list_shops_includes_all_fields(self):
        """Test that all expected fields are included in shop details."""
        response = self.api_client.get(self.url, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        shop = response.data["results"][0]

        # Check all expected fields are present
        expected_fields = [
            "id",
            "name",
            "full_address",
            "street_number",
            "street_name",
            "postal_code",
            "city",
            "latitude",
            "longitude",
            "social_center",
        ]

        for field in expected_fields:
            self.assertIn(field, shop)

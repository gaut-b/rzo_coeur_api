from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from api.enums import UserRole
from api.models import Cashier, Client, CustomUser, Recipient, Shop, SocialCenter, SocialWorker


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


class UserRegistrationTests(APITestCase):
    """Tests for user registration and automatic Client role assignment."""

    def test_registration_creates_client_role(self):
        """Test that registering a user via the API automatically creates a Client role."""
        url = "/api/auth/registration/"
        data = {
            "email": "newclient@test.com",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
            "first_name": "New",
            "last_name": "Client",
        }

        response = self.client.post(url, data, format="json")

        # Verify successful registration
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify user was created
        user = CustomUser.objects.get(email="newclient@test.com")
        self.assertIsNotNone(user)

        # Verify Client role was automatically created
        self.assertTrue(Client.objects.filter(user=user).exists())

        # Verify the user's role property returns CLIENT
        self.assertEqual(user.role, UserRole.CLIENT.value)


class CustomUserSerializerTests(APITestCase):
    """Tests for the CustomUserSerializer with role field."""

    def setUp(self):
        """Set up test data for serializer tests."""
        # Import here to avoid circular import with auth_kit
        from api.users.serializers import CustomUserSerializer

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
        """Test serialization of a user without any role returns UNKNOWN."""
        user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="norole@test.com", password="testpass123", first_name="Sans", last_name="Role"
        )

        serializer = self.CustomUserSerializer(user)
        data = serializer.data

        self.assertEqual(data["email"], "norole@test.com")
        self.assertEqual(data["first_name"], "Sans")
        self.assertEqual(data["last_name"], "Role")
        self.assertEqual(data["role"], "UNKNOWN")

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
        """Test serialization of a user with SOCIAL_WORKER role returns UNKNOWN."""
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
        self.assertEqual(data["role"], "UNKNOWN")

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

    def test_serialize_shop_manager(self):
        """Test serialization of a user with SHOP_MANAGER role returns CASHIER."""
        user = CustomUser.objects.create_user(  # type: ignore[call-arg]
            email="shopmanager@test.com",
            password="testpass123",
            first_name="Manager",
            last_name="Shop",
        )
        Cashier.objects.create(user=user, shop=self.shop, is_shop_manager=True)

        serializer = self.CustomUserSerializer(user)
        data = serializer.data

        self.assertEqual(data["email"], "shopmanager@test.com")
        # Shop managers should be mapped to CASHIER for frontend compatibility
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

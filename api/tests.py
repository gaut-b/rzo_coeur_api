from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from .enums import UserRole
from .models import Cashier, Client, CustomUser, Recipient, Shop, SocialCenter, SocialWorker


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
        self.assertEqual(data["role"], UserRole.CLIENT)

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
        self.assertEqual(data["role"], UserRole.SOCIAL_WORKER)

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
        self.assertEqual(data["role"], UserRole.RECIPIENT)

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
        self.assertEqual(data["role"], UserRole.CASHIER)

    def test_role_field_is_read_only(self):
        """Test that the role field cannot be set during deserialization."""
        data = {
            "email": "newuser@test.com",
            "password": "testpass123",
            "first_name": "New",
            "last_name": "User",
            "role": UserRole.CLIENT,  # Should be ignored
        }

        serializer = self.CustomUserSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # The role field should not be writable
        self.assertNotIn("role", serializer.validated_data)

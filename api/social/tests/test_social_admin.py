from unittest.mock import Mock

from django.test import RequestFactory, TestCase

from api.enums import UserRole
from api.models import CustomUser, SocialCenter, SocialWorker
from api.social.admin import (
    RecipientCreationForm,
    RecipientStaffCreationForm,
    SocialAdminSite,
    SocialWorkerChangeForm,
    SocialWorkerCreationForm,
    SocialWorkerStaffCreationForm,
)


class SocialAdminSiteTests(TestCase):
    """Test cases for SocialAdminSite class"""

    def setUp(self):
        self.site = SocialAdminSite(name="social_admin")
        self.factory = RequestFactory()

    def test_site_configuration(self):
        """Test that SocialAdminSite has correct configuration"""
        self.assertEqual(str(self.site.site_header), "Administration Centre Social")
        self.assertEqual(str(self.site.site_title), "Centre Social")
        self.assertEqual(str(self.site.index_title), "Bienvenue dans l'interface du centre social")

    def test_has_permission_inactive_user(self):
        """Test has_permission returns False for inactive user"""
        request = self.factory.get("/social-admin/")
        request.user = Mock()
        request.user.is_active = False
        request.user.is_staff = False
        request.user.is_authenticated = True
        request.user.role = UserRole.SOCIAL_ADMIN.value

        self.assertFalse(self.site.has_permission(request))


class UniqueEmailCreationFormTests(TestCase):
    """Test duplicate email validation on social admin creation forms."""

    def setUp(self):
        """Create a user whose email will be used to test uniqueness."""
        self.existing_user = CustomUser.objects.create_user(
            email="existing@example.com",
            password="testpass123",
        )
        self.social_center = SocialCenter.objects.create(
            name="Centre Test",
            mail="centre@test.com",
        )
        self.request = Mock()
        self.request.user = Mock()
        self.request.user.is_staff = True
        self.request.user.socialworker = Mock()
        self.request.user.socialworker.social_center = self.social_center

    def _base_data(self, email="new@example.com"):
        return {
            "email": email,
            "first_name": "Prénom",
            "last_name": "Nom",
        }

    def test_recipient_creation_form_rejects_duplicate_email(self):
        """RecipientCreationForm raises validation error for existing email."""
        form = RecipientCreationForm(
            data={**self._base_data("existing@example.com"), "social_center": self.social_center.pk},
            request=self.request,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_recipient_staff_creation_form_rejects_duplicate_email(self):
        """RecipientStaffCreationForm raises validation error for existing email."""
        form = RecipientStaffCreationForm(
            data={**self._base_data("existing@example.com"), "social_center": self.social_center.pk},
            request=self.request,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_social_worker_creation_form_rejects_duplicate_email(self):
        """SocialWorkerCreationForm raises validation error for existing email."""
        form = SocialWorkerCreationForm(
            data=self._base_data("existing@example.com"),
            request=self.request,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_social_worker_staff_creation_form_rejects_duplicate_email(self):
        """SocialWorkerStaffCreationForm raises validation error for existing email."""
        form = SocialWorkerStaffCreationForm(
            data={**self._base_data("existing@example.com"), "social_center": self.social_center.pk},
            request=self.request,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_creation_form_accepts_new_email(self):
        """RecipientCreationForm passes validation for a fresh email address."""
        form = RecipientCreationForm(
            data={**self._base_data("brand_new@example.com"), "social_center": self.social_center.pk},
            request=self.request,
        )
        self.assertTrue(form.is_valid(), form.errors)


class UniqueEmailChangeFormTests(TestCase):
    """Test duplicate email validation on social admin change forms."""

    def setUp(self):
        """Create two users: one to edit, one whose email is already taken."""
        self.social_center = SocialCenter.objects.create(
            name="Centre Test",
            mail="centre@test.com",
        )
        self.user_a = CustomUser.objects.create_user(
            email="user_a@example.com",
            password="testpass123",
        )
        self.worker_a = SocialWorker.objects.create(
            user=self.user_a,
            social_center=self.social_center,
        )
        self.user_b = CustomUser.objects.create_user(
            email="user_b@example.com",
            password="testpass123",
        )
        self.worker_b = SocialWorker.objects.create(
            user=self.user_b,
            social_center=self.social_center,
        )

    def test_change_form_rejects_email_taken_by_another_user(self):
        """Change form raises error if email belongs to a different user."""
        form = SocialWorkerChangeForm(
            data={
                "email": "user_b@example.com",
                "first_name": "Prénom",
                "last_name": "Nom",
                "social_center": self.social_center.pk,
                "is_social_admin": False,
            },
            instance=self.worker_a,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_change_form_allows_keeping_own_email(self):
        """Change form is valid when the user keeps their current email."""
        form = SocialWorkerChangeForm(
            data={
                "email": "user_a@example.com",
                "first_name": "Prénom",
                "last_name": "Nom",
                "social_center": self.social_center.pk,
                "is_social_admin": False,
            },
            instance=self.worker_a,
        )
        self.assertTrue(form.is_valid(), form.errors)

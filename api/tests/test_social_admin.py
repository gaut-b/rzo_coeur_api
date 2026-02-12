from unittest.mock import Mock

from django.test import RequestFactory, TestCase

from api.admin import SocialAdminSite
from api.enums import UserRole


class SocialAdminSiteTests(TestCase):
    """Test cases for SocialAdminSite class"""

    def setUp(self):
        self.site = SocialAdminSite(name="social_admin")
        self.factory = RequestFactory()

    def test_site_configuration(self):
        """Test that SocialAdminSite has correct configuration"""
        self.assertEqual(self.site.site_header, "Social Center Admin")
        self.assertEqual(self.site.site_title, "Social Center")
        self.assertEqual(self.site.index_title, "Welcome to social center interface")

    def test_check_user_permission_with_social_admin(self):
        """Test check_user_permission returns True for social admin users"""
        user = Mock()
        user.role = UserRole.SOCIAL_ADMIN.value

        self.assertTrue(self.site.check_user_permission(user))

    def test_check_user_permission_with_non_social_admin(self):
        """Test check_user_permission returns False for non-social admin users"""
        user = Mock()
        user.role = UserRole.CLIENT.value

        self.assertFalse(self.site.check_user_permission(user))

    def test_get_permission_denied_message(self):
        """Test custom permission denied message"""
        expected_message = "You do not have permission to access the social center admin page."
        self.assertEqual(self.site.get_permission_denied_message(), expected_message)

    def test_has_permission_authenticated_social_admin(self):
        """Test has_permission returns True for authenticated social admin"""
        request = self.factory.get("/social-admin/")
        request.user = Mock()
        request.user.is_active = True
        request.user.is_authenticated = True
        request.user.role = UserRole.SOCIAL_ADMIN.value

        self.assertTrue(self.site.has_permission(request))

    def test_has_permission_unauthenticated_user(self):
        """Test has_permission returns False for unauthenticated user"""
        request = self.factory.get("/social-admin/")
        request.user = Mock()
        request.user.is_active = True
        request.user.is_authenticated = False

        self.assertFalse(self.site.has_permission(request))

    def test_has_permission_inactive_user(self):
        """Test has_permission returns False for inactive user"""
        request = self.factory.get("/social-admin/")
        request.user = Mock()
        request.user.is_active = False
        request.user.is_authenticated = True
        request.user.role = UserRole.SOCIAL_ADMIN.value

        self.assertFalse(self.site.has_permission(request))

    def test_has_permission_wrong_role(self):
        """Test has_permission returns False for user with wrong role"""
        request = self.factory.get("/social-admin/")
        request.user = Mock()
        request.user.is_active = True
        request.user.is_authenticated = True
        request.user.role = UserRole.CLIENT.value

        self.assertFalse(self.site.has_permission(request))

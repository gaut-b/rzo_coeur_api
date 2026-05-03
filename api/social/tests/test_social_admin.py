from unittest.mock import Mock

from django.test import RequestFactory, TestCase

from api.enums import UserRole
from api.social.admin import SocialAdminSite


class SocialAdminSiteTests(TestCase):
    """Test cases for SocialAdminSite class"""

    def setUp(self):
        self.site = SocialAdminSite(name="social_admin")
        self.factory = RequestFactory()

    def test_site_configuration(self):
        """Test that SocialAdminSite has correct configuration"""
        self.assertEqual(self.site.site_header, "Administration Centre Social")
        self.assertEqual(self.site.site_title, "Centre Social")
        self.assertEqual(self.site.index_title, "Bienvenue dans l'interface du centre social")

    def test_has_permission_inactive_user(self):
        """Test has_permission returns False for inactive user"""
        request = self.factory.get("/social-admin/")
        request.user = Mock()
        request.user.is_active = False
        request.user.is_staff = False
        request.user.is_authenticated = True
        request.user.role = UserRole.SOCIAL_ADMIN.value

        self.assertFalse(self.site.has_permission(request))

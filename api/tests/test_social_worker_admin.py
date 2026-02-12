from unittest.mock import MagicMock, PropertyMock, patch

from django.test import TestCase

from api.admin import SocialWorkerAdmin

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_admin():
    """Return a SocialWorkerAdmin instance bound to a dummy site."""
    site = MagicMock()
    return SocialWorkerAdmin(MagicMock(), site)


def _make_social_center(name="Center A"):
    sc = MagicMock()
    sc.name = name
    return sc


def _make_request(
    *,
    authenticated=True,
    has_socialworker=True,
    is_social_admin=True,
    has_cashier=False,
    social_center=None,
    user_obj=None,
):
    """
    Build a mock request whose .user attribute mimics the expected structure.
    """
    request = MagicMock()
    user = MagicMock() if user_obj is None else user_obj
    user.is_authenticated = authenticated

    if social_center is None:
        social_center = _make_social_center()

    if has_socialworker:
        sw = MagicMock()
        sw.is_social_admin = is_social_admin
        sw.social_center = social_center
        user.socialworker = sw
        # Make hasattr(user, 'socialworker') return True
        type(user).socialworker = PropertyMock(return_value=sw)
    else:
        # Remove socialworker attribute so hasattr returns False
        if hasattr(type(user), "socialworker"):
            del type(user).socialworker
        try:
            del user.socialworker
        except AttributeError:
            pass

    if has_cashier:
        cashier = MagicMock()
        user.cashier = cashier
        type(user).cashier = PropertyMock(return_value=cashier)
    else:
        try:
            del user.cashier
        except AttributeError:
            pass

    request.user = user
    return request


def _make_obj(social_center=None, user=None):
    """Return a mock SocialWorker object."""
    obj = MagicMock()
    obj.social_center = social_center or _make_social_center()
    obj.user = user or MagicMock()
    return obj


class TestSocialWorkerAdminGetQueryset(TestCase):
    """Tests for get_queryset."""

    def setUp(self):
        self.admin = _make_admin()

    def test_filters_by_logged_in_users_social_center(self):
        sc = _make_social_center("Center B")
        request = _make_request(social_center=sc)
        fake_qs = MagicMock()
        fake_qs.filter.return_value = fake_qs

        with patch.object(self.admin.__class__.__bases__[0], "get_queryset", return_value=fake_qs):
            result = self.admin.get_queryset(request)

        fake_qs.filter.assert_called_once_with(social_center=sc)
        self.assertEqual(result, fake_qs)

    def test_returns_none_queryset_when_no_socialworker(self):
        request = _make_request(has_socialworker=False)
        fake_qs = MagicMock()
        fake_qs.none.return_value = "empty_qs"

        with patch.object(self.admin.__class__.__bases__[0], "get_queryset", return_value=fake_qs):
            result = self.admin.get_queryset(request)

        self.assertEqual(result, "empty_qs")


class TestIsFromSameSocialCenter(TestCase):
    """Tests for the is_from_same_social_center helper."""

    def setUp(self):
        self.admin = _make_admin()

    def _request_with_cashier_attr(self, sc, is_admin=True, same_user=False):
        """
        Build a request where the user has BOTH .cashier and .socialworker attributes,
        mirroring the actual condition in is_from_same_social_center.
        """
        request = MagicMock()
        user = MagicMock()
        user.is_authenticated = True

        sw = MagicMock()
        sw.is_social_admin = is_admin
        sw.social_center = sc
        user.socialworker = sw
        type(user).socialworker = PropertyMock(return_value=sw)

        cashier = MagicMock()
        user.cashier = cashier
        type(user).cashier = PropertyMock(return_value=cashier)

        request.user = user
        return request

    def test_returns_true_when_all_conditions_met(self):
        sc = _make_social_center()
        request = self._request_with_cashier_attr(sc, is_admin=True)
        obj = _make_obj(social_center=sc)
        obj.user = MagicMock()  # different from request.user

        result = self.admin.is_from_same_social_center(request, obj)
        self.assertTrue(result)

    def test_returns_false_when_user_has_no_cashier(self):
        """The check explicitly requires hasattr(request.user, 'cashier')."""
        sc = _make_social_center()
        request = _make_request(has_socialworker=True, is_social_admin=True, has_cashier=False, social_center=sc)
        obj = _make_obj(social_center=sc)

        result = self.admin.is_from_same_social_center(request, obj)
        self.assertFalse(result)

    def test_returns_false_when_not_social_admin(self):
        sc = _make_social_center()
        request = self._request_with_cashier_attr(sc, is_admin=False)
        obj = _make_obj(social_center=sc)

        result = self.admin.is_from_same_social_center(request, obj)
        self.assertFalse(result)

    def test_returns_false_when_different_social_center(self):
        sc1 = _make_social_center("Center 1")
        sc2 = _make_social_center("Center 2")
        request = self._request_with_cashier_attr(sc1, is_admin=True)
        obj = _make_obj(social_center=sc2)

        result = self.admin.is_from_same_social_center(request, obj)
        self.assertFalse(result)

    def test_returns_false_when_obj_user_is_request_user(self):
        sc = _make_social_center()
        request = self._request_with_cashier_attr(sc, is_admin=True)
        obj = _make_obj(social_center=sc)
        obj.user = request.user  # same user

        result = self.admin.is_from_same_social_center(request, obj)
        self.assertFalse(result)

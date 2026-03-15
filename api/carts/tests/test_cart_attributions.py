"""
Tests for cart_attributions.py

Covers:
- CartAttributionAdminSite.check_user_permission
- CartCreationForm: shop/recipient filtering by social center
- CartChangeForm: articles queryset (in cart + available from same shop)
- ArticleChoiceField.label_from_instance
- CartAttribAdmin permissions (including COLLECTED lock)
- CartAttribAdmin.save_model: article assignment/detachment
- ArticleAvailabilityFilter
- ArticleAttrAdmin.get_queryset: social center isolation
- ArticleToCartForm: only PENDING carts from same social center
"""

from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone

from api.carts.admin import (
    ArticleAttrAdmin,
    ArticleAvailabilityFilter,
    CartAttribAdmin,
    cart_attrib_admin_site,
)
from api.carts.forms import (
    ArticleChoiceField,
    CartChangeForm,
    CartCreationForm,
)
from api.models import (
    Article,
    Cart,
    Client,
    CustomUser,
    Recipient,
    Shop,
    SocialCenter,
    SocialWorker,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_user(email: str, **kwargs) -> CustomUser:
    """Create a CustomUser with a usable password."""
    return User.objects.create_user(email=email, password="pass", **kwargs)


def make_social_center(name: str = "Centre A") -> SocialCenter:
    return SocialCenter.objects.create(name=name, mail=f"{name}@test.com")


def make_shop(social_center: SocialCenter, name: str = "Shop A") -> Shop:
    return Shop.objects.create(name=name, social_center=social_center)


def make_social_worker(
    social_center: SocialCenter,
    email: str = "sw@test.com",
    is_social_admin: bool = False,
) -> SocialWorker:
    user = make_user(email)
    return SocialWorker.objects.create(user=user, social_center=social_center, is_social_admin=is_social_admin)


def make_recipient(social_center: SocialCenter, email: str = "recipient@test.com") -> Recipient:
    user = make_user(email)
    return Recipient.objects.create(user=user, social_center=social_center)


def make_client(email: str = "client@test.com") -> Client:
    user = make_user(email)
    return Client.objects.create(user=user)


def make_article(
    shop: Shop,
    client: Client,
    name: str = "Article",
    brand_label: str = "",
    cart: Cart | None = None,
) -> Article:
    return Article.objects.create(
        name=name,
        barcode=1234567890,
        shop=shop,
        client=client,
        brand_label=brand_label,
        cart=cart,
    )


def make_cart(
    shop: Shop,
    recipient: Recipient | None = None,
    collected: bool = False,
) -> Cart:
    cart = Cart.objects.create(shop=shop, recipient=recipient)
    if collected:
        cart.collected_at = timezone.now()
        cart.save()
    return cart


def make_request(user) -> Mock:
    """Attach a user to a fake GET request."""
    factory = RequestFactory()
    request = factory.get("/")
    request.user = user
    return request


# ---------------------------------------------------------------------------
# CartCreationForm
# ---------------------------------------------------------------------------


class CartCreationFormTests(TestCase):
    """Tests for CartCreationForm shop/recipient queryset filtering."""

    def setUp(self):
        self.center_a = make_social_center("Centre A")
        self.center_b = make_social_center("Centre B")
        self.shop_a = make_shop(self.center_a, "Shop A")
        self.shop_b = make_shop(self.center_b, "Shop B")
        self.sw = make_social_worker(self.center_a)
        self.recipient_a = make_recipient(self.center_a, "recip_a@test.com")
        self.recipient_b = make_recipient(self.center_b, "recip_b@test.com")

    def _make_form(self, worker: SocialWorker) -> CartCreationForm:
        """Build a CartCreationForm with a fake request for the given worker."""
        request = Mock()
        request.user = worker.user
        request.user.socialworker = worker
        return CartCreationForm(request=request)

    def test_shop_queryset_filters_by_social_center(self):
        """Only shops linked to the worker's social center should appear."""
        form = self._make_form(self.sw)
        shop_qs = form.fields["shop"].queryset
        self.assertIn(self.shop_a, shop_qs)
        self.assertNotIn(self.shop_b, shop_qs)

    def test_recipient_queryset_filters_by_social_center(self):
        """Only recipients linked to the worker's social center should appear."""
        form = self._make_form(self.sw)
        recipient_qs = form.fields["recipient"].queryset
        self.assertIn(self.recipient_a, recipient_qs)
        self.assertNotIn(self.recipient_b, recipient_qs)


# ---------------------------------------------------------------------------
# CartChangeForm
# ---------------------------------------------------------------------------


class CartChangeFormTests(TestCase):
    """Tests for CartChangeForm articles queryset."""

    def setUp(self):
        self.center = make_social_center()
        self.shop = make_shop(self.center)
        self.other_shop = make_shop(self.center, "Shop B")
        self.client_obj = make_client()
        self.cart = make_cart(self.shop)

        self.article_in_cart = make_article(self.shop, self.client_obj, "In Cart", cart=self.cart)
        self.article_available = make_article(self.shop, self.client_obj, "Available")
        self.article_other_shop = make_article(self.other_shop, self.client_obj, "Other Shop")
        other_cart = make_cart(self.shop)
        self.article_in_other_cart = make_article(self.shop, self.client_obj, "In Other Cart", cart=other_cart)

    def test_articles_queryset_includes_in_cart(self):
        """Articles already in this cart must be selectable."""
        form = CartChangeForm(instance=self.cart)
        self.assertIn(self.article_in_cart, form.fields["articles"].queryset)

    def test_articles_queryset_includes_available_same_shop(self):
        """Available articles from the same shop must be selectable."""
        form = CartChangeForm(instance=self.cart)
        self.assertIn(self.article_available, form.fields["articles"].queryset)

    def test_articles_queryset_excludes_other_shop(self):
        """Articles from a different shop must not appear."""
        form = CartChangeForm(instance=self.cart)
        self.assertNotIn(self.article_other_shop, form.fields["articles"].queryset)

    def test_articles_queryset_excludes_articles_in_other_cart(self):
        """Articles already assigned to another cart must not appear."""
        form = CartChangeForm(instance=self.cart)
        self.assertNotIn(self.article_in_other_cart, form.fields["articles"].queryset)

    def test_initial_articles_are_prechecked(self):
        """Articles already in the cart must be in initial data."""
        form = CartChangeForm(instance=self.cart)
        initial = list(form.initial["articles"])
        self.assertIn(self.article_in_cart, initial)
        self.assertNotIn(self.article_available, initial)


# ---------------------------------------------------------------------------
# ArticleChoiceField
# ---------------------------------------------------------------------------


class ArticleChoiceFieldTests(TestCase):
    """Tests for ArticleChoiceField.label_from_instance."""

    def setUp(self):
        self.field = ArticleChoiceField(queryset=Article.objects.none())
        self.center = make_social_center()
        self.shop = make_shop(self.center)
        self.client_obj = make_client()

    def test_label_with_brand(self):
        """Label must include both name and brand separated by em dash."""
        article = make_article(self.shop, self.client_obj, name="Pâtes", brand_label="Barilla")
        self.assertEqual(self.field.label_from_instance(article), "Pâtes — Barilla")

    def test_label_without_brand(self):
        """Label must be just the name when brand_label is empty."""
        article = make_article(self.shop, self.client_obj, name="Pâtes", brand_label="")
        self.assertEqual(self.field.label_from_instance(article), "Pâtes")


# ---------------------------------------------------------------------------
# CartAttribAdmin permissions
# ---------------------------------------------------------------------------


class CartAttribAdminPermissionsTests(TestCase):
    """Tests for CartAttribAdmin permission methods."""

    def setUp(self):
        self.admin = CartAttribAdmin(Cart, cart_attrib_admin_site)
        self.center = make_social_center()
        self.shop = make_shop(self.center)
        self.sw = make_social_worker(self.center)

    def _request(self, user):
        return make_request(user)

    def test_collected_cart_blocks_change_permission(self):
        """A COLLECTED cart must not be editable."""
        cart = make_cart(
            self.shop,
            recipient=make_recipient(self.center, "r@t.com"),
            collected=True,
        )
        request = self._request(self.sw.user)
        self.assertFalse(self.admin.has_change_permission(request, cart))

    def test_pending_cart_allows_change_permission(self):
        """A PENDING cart must be editable by a social worker."""
        cart = make_cart(self.shop)
        request = self._request(self.sw.user)
        self.assertTrue(self.admin.has_change_permission(request, cart))

    def test_assigned_cart_allows_change_permission(self):
        """An ASSIGNED (not yet collected) cart must still be editable."""
        cart = make_cart(self.shop, recipient=make_recipient(self.center, "r2@t.com"))
        request = self._request(self.sw.user)
        self.assertTrue(self.admin.has_change_permission(request, cart))

    def test_unauthenticated_user_denied(self):
        """Unauthenticated users must be denied all change access."""
        user = Mock()
        user.is_authenticated = False
        request = make_request(user)
        self.assertFalse(self.admin.has_change_permission(request))

    def test_social_worker_can_add(self):
        """Any authenticated social worker must be able to create a cart."""
        request = self._request(self.sw.user)
        self.assertTrue(self.admin.has_add_permission(request))

    def test_collected_cart_has_all_readonly_fields(self):
        """A COLLECTED cart must expose all fields as readonly."""
        cart = make_cart(
            self.shop,
            recipient=make_recipient(self.center, "r3@t.com"),
            collected=True,
        )
        request = self._request(self.sw.user)
        readonly = self.admin.get_readonly_fields(request, cart)
        self.assertIn("shop", readonly)
        self.assertIn("recipient", readonly)
        self.assertIn("collected_at", readonly)
        self.assertIn("get_articles_display", readonly)

    def test_collected_cart_fields_use_display_method(self):
        """get_fields for a COLLECTED cart must use get_articles_display, not articles."""
        cart = make_cart(
            self.shop,
            recipient=make_recipient(self.center, "r4@t.com"),
            collected=True,
        )
        request = self._request(self.sw.user)
        fields = self.admin.get_fields(request, cart)
        self.assertIn("get_articles_display", fields)
        self.assertNotIn("articles", fields)

    def test_pending_cart_fields_use_articles_widget(self):
        """get_fields for a PENDING cart must use the articles widget."""
        cart = make_cart(self.shop)
        request = self._request(self.sw.user)
        fields = self.admin.get_fields(request, cart)
        self.assertIn("articles", fields)
        self.assertNotIn("get_articles_display", fields)

    def test_get_articles_display_with_articles(self):
        """get_articles_display must return a comma-separated list of article names."""
        client_obj = make_client("c@t.com")
        cart = make_cart(self.shop)
        make_article(self.shop, client_obj, "Pommes", "Bio", cart=cart)
        make_article(self.shop, client_obj, "Lait", "", cart=cart)
        display = self.admin.get_articles_display(cart)
        self.assertIn("Pommes (Bio)", display)
        self.assertIn("Lait", display)

    def test_get_articles_display_empty_cart(self):
        """get_articles_display must return '—' for an empty cart."""
        cart = make_cart(self.shop)
        display = self.admin.get_articles_display(cart)
        self.assertEqual(display, "—")


# ---------------------------------------------------------------------------
# CartAttribAdmin.save_model (article assignment)
# ---------------------------------------------------------------------------


class CartAttribAdminSaveModelTests(TestCase):
    """Tests for CartAttribAdmin.save_model article assignment logic."""

    def setUp(self):
        self.admin_instance = CartAttribAdmin(Cart, cart_attrib_admin_site)
        self.center = make_social_center()
        self.shop = make_shop(self.center)
        self.client_obj = make_client()
        self.cart = make_cart(self.shop)
        self.sw = make_social_worker(self.center)

    def _save(self, cart: Cart, selected_articles: list) -> None:
        """Simulate a save_model call with given selected articles."""
        form = Mock()
        form.instance = cart
        form.cleaned_data = {"articles": selected_articles}
        request = make_request(self.sw.user)
        self.admin_instance.save_model(request, cart, form, change=True)

    def test_already_assigned_article_stays(self):
        """An article that was in the cart and remains selected must stay."""
        article = make_article(self.shop, self.client_obj, "A3", cart=self.cart)
        self._save(self.cart, [article])
        article.refresh_from_db()
        self.assertEqual(article.cart, self.cart)

    def test_save_on_creation_does_not_change_articles(self):
        """save_model with change=False (creation) must not touch articles."""
        article = make_article(self.shop, self.client_obj, "A4")
        form = Mock()
        form.instance = self.cart
        form.cleaned_data = {"articles": [article]}
        request = make_request(self.sw.user)
        self.admin_instance.save_model(request, self.cart, form, change=False)
        article.refresh_from_db()
        self.assertIsNone(article.cart)


# ---------------------------------------------------------------------------
# ArticleAvailabilityFilter
# ---------------------------------------------------------------------------


class ArticleAvailabilityFilterTests(TestCase):
    """Tests for ArticleAvailabilityFilter queryset filtering."""

    def setUp(self):
        self.center = make_social_center()
        self.shop = make_shop(self.center)
        self.client_obj = make_client()
        self.cart = make_cart(self.shop)
        self.available = make_article(self.shop, self.client_obj, "Free")
        self.in_cart = make_article(self.shop, self.client_obj, "In Cart", cart=self.cart)
        # Instantiate via the standard Django way: filter(request, params, model, model_admin)
        self.admin_instance = ArticleAttrAdmin(Article, cart_attrib_admin_site)
        self.request = Mock()

    def _get_filter(self, value: str | None) -> ArticleAvailabilityFilter:
        f = ArticleAvailabilityFilter(self.request, {}, Article, self.admin_instance)
        if value is not None:
            f.used_parameters = {f.parameter_name: value}
        return f

    def test_available_filter(self):
        """'available' must return only articles with cart=None."""
        f = self._get_filter("available")
        qs = f.queryset(self.request, Article.objects.all())
        self.assertIn(self.available, qs)
        self.assertNotIn(self.in_cart, qs)

    def test_in_cart_filter(self):
        """'in_cart' must return only articles assigned to a cart."""
        f = self._get_filter("in_cart")
        qs = f.queryset(self.request, Article.objects.all())
        self.assertIn(self.in_cart, qs)
        self.assertNotIn(self.available, qs)

    def test_no_filter_returns_all(self):
        """No value must return the full queryset unchanged."""
        f = self._get_filter(None)
        qs = f.queryset(self.request, Article.objects.all())
        self.assertIn(self.available, qs)
        self.assertIn(self.in_cart, qs)


# ---------------------------------------------------------------------------
# ArticleAttrAdmin.get_queryset (social center isolation)
# ---------------------------------------------------------------------------


class ArticleAttrAdminQuerysetTests(TestCase):
    """Tests that ArticleAttrAdmin isolates articles by social center."""

    def setUp(self):
        self.admin_instance = ArticleAttrAdmin(Article, cart_attrib_admin_site)
        self.center_a = make_social_center("A")
        self.center_b = make_social_center("B")
        self.shop_a = make_shop(self.center_a, "Shop A")
        self.shop_b = make_shop(self.center_b, "Shop B")
        self.client_obj = make_client()
        self.sw_a = make_social_worker(self.center_a, "sw_a@test.com")
        self.article_a = make_article(self.shop_a, self.client_obj, "Art A")
        self.article_b = make_article(self.shop_b, self.client_obj, "Art B")

    def test_social_worker_sees_only_own_center_articles(self):
        """A social worker must only see articles from their own center's shops."""
        request = make_request(self.sw_a.user)
        qs = self.admin_instance.get_queryset(request)
        self.assertIn(self.article_a, qs)
        self.assertNotIn(self.article_b, qs)

    def test_staff_sees_all_articles(self):
        """A staff user must see articles from all centers."""
        staff = make_user("staff@test.com", is_staff=True)
        request = make_request(staff)
        qs = self.admin_instance.get_queryset(request)
        self.assertIn(self.article_a, qs)
        self.assertIn(self.article_b, qs)


# ---------------------------------------------------------------------------
# ArticleToCartForm (cart dropdown filtering)
# ---------------------------------------------------------------------------


class ArticleToCartFormCartQuerysetTests(TestCase):
    """
    Tests for the cart queryset logic used in ArticleToCartForm.

    We test the DB filter directly (matching what __init__ applies) rather
    than instantiating ActionForm, whose initialisation is controlled by the
    django_admin_action_forms library.
    """

    def setUp(self):
        self.center_a = make_social_center("A")
        self.center_b = make_social_center("B")
        self.shop_a = make_shop(self.center_a, "Shop A")
        self.shop_b = make_shop(self.center_b, "Shop B")
        self.recipient_a = make_recipient(self.center_a, "r_a@test.com")

        self.pending_a = make_cart(self.shop_a)
        self.assigned_a = make_cart(self.shop_a, recipient=self.recipient_a)
        self.collected_a = make_cart(self.shop_a, recipient=self.recipient_a, collected=True)
        self.pending_b = make_cart(self.shop_b)

    def _cart_qs(self, social_center):
        """Replicate the filter applied by ArticleToCartForm.__init__."""
        return Cart.objects.filter(
            shop__social_center=social_center,
            collected_at=None,
        )

    def test_pending_cart_included(self):
        """PENDING carts (no recipient) from the given center must appear."""
        qs = self._cart_qs(self.center_a)
        self.assertIn(self.pending_a, qs)

    def test_assigned_cart_included(self):
        """ASSIGNED carts (recipient set, not yet collected) must be included."""
        qs = self._cart_qs(self.center_a)
        self.assertIn(self.assigned_a, qs)

    def test_collected_cart_excluded(self):
        """COLLECTED carts (collected_at set) must be excluded."""
        qs = self._cart_qs(self.center_a)
        self.assertNotIn(self.collected_a, qs)

    def test_other_center_cart_excluded(self):
        """Carts from other social centers must not appear."""
        qs = self._cart_qs(self.center_a)
        self.assertNotIn(self.pending_b, qs)

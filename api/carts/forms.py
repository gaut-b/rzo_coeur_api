from django import forms
from django.db.models import Q
from django_admin_action_forms import ActionForm

from api.models import Article, Cart, Recipient, Shop


class CartCreationForm(forms.ModelForm):
    """
    Creation form for a new cart.

    Accepts an optional ``request`` kwarg.  When provided and the requesting
    user has a social worker profile, the shop and recipient querysets are
    restricted to the worker's social center.  This filtering is also applied
    by ``CartAttribAdmin.formfield_for_foreignkey`` in the admin context.
    """

    class Meta:
        model = Cart
        fields = ["shop", "recipient"]

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        if request is not None and hasattr(request.user, "socialworker"):
            sc = request.user.socialworker.social_center
            self.fields["shop"].queryset = Shop.objects.filter(social_center=sc)
            self.fields["recipient"].queryset = Recipient.objects.filter(social_center=sc)


class ArticleChoiceField(forms.ModelMultipleChoiceField):
    """ModelMultipleChoiceField that appends the brand label to each option."""

    def label_from_instance(self, obj: Article) -> str:
        """Return 'Article name — Brand' or just 'Article name'."""
        if obj.brand_label:
            return f"{obj.name} — {obj.brand_label}"
        return obj.name


class CartChangeForm(forms.ModelForm):
    """
    Form for editing an existing cart.

    Displays articles already in this cart and available articles
    from the same shop as checkboxes.
    """

    articles = ArticleChoiceField(
        queryset=Article.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Articles dans le panier",
    )

    class Meta:
        model = Cart
        fields = ["recipient"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Selectable articles: those already in this cart, or available
            # (cart=None) articles from the same shop.
            qs = Article.objects.filter(Q(cart=self.instance) | Q(cart=None, shop=self.instance.shop)).order_by("name")
            self.fields["articles"].queryset = qs
            # Pre-check only the articles currently in this cart.
            self.initial["articles"] = Article.objects.filter(cart=self.instance)


class ArticleToCartForm(ActionForm):
    """Action form to assign selected articles to a cart."""

    cart = forms.ModelChoiceField(queryset=Cart.objects.all())

    def __init__(self, *args, **kwargs):
        """Filter the cart dropdown to carts from the worker's social center."""
        super().__init__(*args, **kwargs)
        if hasattr(self, "request") and hasattr(self.request.user, "socialworker"):
            social_center = self.request.user.socialworker.social_center
            self.fields["cart"].queryset = Cart.objects.filter(
                shop__social_center=social_center,
                collected_at=None,
            )

    def clean_cart(self):
        cart = self.cleaned_data["cart"]
        if cart.status == "COLLECTED":
            raise forms.ValidationError("Cart is already Collected")
        ref_shop = self.queryset.first().shop
        for article in self.queryset:
            if article.cart is not None:
                raise forms.ValidationError("An article is already assigned to a cart")
            if article.shop != ref_shop:
                raise forms.ValidationError("Articles are not from same shop")
        if cart.shop != ref_shop:
            raise forms.ValidationError("Cart and Articles are not from same shop")
        return cart

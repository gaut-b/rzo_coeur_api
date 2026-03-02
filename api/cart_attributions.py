from django import forms
from django.contrib import admin
from django.db.models import Q
from django.urls import reverse
from django.utils.html import format_html, mark_safe
from django_admin_action_forms import ActionForm, AdminActionFormsMixin, action_with_form

from .admin import CustomAdminSite
from .enums import UserRole
from .models import (
    Article,
    Cart,
    Recipient,
    Shop,
)


class CartCreationForm(forms.ModelForm):
    shop = forms.ModelChoiceField(queryset=Shop.objects.none())

    class Meta:
        model = Cart
        fields = ["shop", "recipient"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        social_center = self.request.user.socialworker.social_center
        self.fields["shop"].queryset = Shop.objects.filter(social_center=social_center)
        self.fields["recipient"].queryset = Recipient.objects.filter(social_center=social_center)

    def save(self, commit=True):
        if not self.request or not (self.request.user.is_staff or hasattr(self.request.user, "socialworker")):
            raise forms.ValidationError("Cannot create cart, insufficient rights.")

        cart = super().save(commit=False)
        cart.shop = self.cleaned_data["shop"]

        if commit:
            cart.save()
        return cart


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
            shop = self.instance.shop
            qs = Article.objects.filter(Q(cart=self.instance) | Q(shop=shop, cart=None)).order_by("name")
            self.fields["articles"].queryset = qs
            self.initial["articles"] = Article.objects.filter(cart=self.instance)


class CartAttribAdmin(admin.ModelAdmin):
    list_display = ["id", "shop", "status", "collected_at"]

    def get_fields(self, request, obj=None):
        """Different fields for creation vs editing."""
        if obj is None:
            return ["shop", "recipient"]
        return ["shop", "recipient", "collected_at", "articles"]

    def get_readonly_fields(self, request, obj=None):
        """Shop and collected_at are readonly when editing."""
        if obj is None:
            return []
        return ["shop", "collected_at"]

    # Cart should have a social center attribute as well as shop
    def get_form(self, request, obj=None, **kwargs):
        """Use custom form for creation, standard form for editing."""
        if obj is None:  # Creating new cart
            kwargs["form"] = CartCreationForm
            form_class = super().get_form(request, obj, **kwargs)

            # Create a wrapper that injects request into form instantiation
            class FormWithRequest(form_class):
                def __init__(self, *args, **form_kwargs):
                    form_kwargs["request"] = request
                    super().__init__(*args, **form_kwargs)

            return FormWithRequest
        kwargs["form"] = CartChangeForm
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        """
        Save the cart then update article assignments.

        For each article in the shop: assign it to this cart if selected,
        detach it (cart=None) if deselected.
        """
        super().save_model(request, obj, form, change)
        if change and "articles" in form.cleaned_data:
            selected_articles = set(form.cleaned_data["articles"])
            previously_in_cart = set(Article.objects.filter(cart=obj))
            for article in selected_articles - previously_in_cart:
                article.cart = obj
                article.save()
            for article in previously_in_cart - selected_articles:
                article.cart = None
                article.save()

    # Permissions are to check if user is social worker or superuser
    # add, change, delete and view are reserved to social worker or superuser
    def has_view_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        return hasattr(request.user, "socialworker") or request.user.is_staff

    def has_add_permission(self, request):
        return request.user.is_staff or (request.user.is_authenticated and hasattr(request.user, "socialworker"))

    def has_change_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if obj is not None and obj.status == "COLLECTED":
            return False
        return request.user.is_staff or hasattr(request.user, "socialworker")

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        return request.user.is_staff or hasattr(request.user, "socialworker")

    def has_module_permission(self, request):
        return request.user.is_staff or (request.user.is_authenticated and hasattr(request.user, "socialworker"))


class CartAttributionAdminSite(CustomAdminSite):
    site_header = "Cart Attribution"
    site_title = "Cart Attribution"
    index_title = "Interface de création et attribution de paniers"

    def check_user_permission(self, user):
        """Check if user has a social worker or a social admin role."""
        return user.role == UserRole.SOCIAL_ADMIN.value or user.role == UserRole.SOCIAL_WORKER.value

    def get_permission_denied_message(self):
        """Custom message for social admin access denied."""
        return "You do not have permission to access the social center admin page."


class RecipientAttrAdmin(admin.ModelAdmin):
    list_display = ["get_email", "get_first_name", "get_last_name"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]

    def get_email(self, obj):
        return obj.user.email

    get_email.short_description = "Email"
    get_email.admin_order_field = "user__email"

    def get_first_name(self, obj):
        return obj.user.first_name

    get_first_name.short_description = "First Name"
    get_first_name.admin_order_field = "user__first_name"

    def get_last_name(self, obj):
        return obj.user.last_name

    get_last_name.short_description = "Last Name"
    get_last_name.admin_order_field = "user__last_name"

    def is_from_same_social_center(self, request, obj):
        return hasattr(request.user, "socialworker") and obj.social_center == request.user.socialworker.social_center

    # Permissions are to check if social worker or social admin
    # add, change, delete and view are reserved to social center admin or superuser
    def has_view_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if obj is None:
            return hasattr(request.user, "socialworker") or request.user.is_staff
        return self.is_from_same_social_center(request, obj) or request.user.is_staff

    def has_module_permission(self, request):
        return request.user.is_staff or (request.user.is_authenticated and hasattr(request.user, "socialworker"))


class ArticleToCartForm(ActionForm):
    cart = forms.ModelChoiceField(queryset=Cart.objects.all())

    def __init__(self, *args, **kwargs):
        """Filter the cart dropdown to carts from the worker's social center."""
        super().__init__(*args, **kwargs)
        if hasattr(self, "request") and hasattr(self.request.user, "socialworker"):
            social_center = self.request.user.socialworker.social_center
            self.fields["cart"].queryset = Cart.objects.filter(
                shop__social_center=social_center,
                recipient=None,
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


class ArticleAvailabilityFilter(admin.SimpleListFilter):
    """Filter articles by availability: available (cart=None) or in a cart."""

    title = "Disponibilité"
    parameter_name = "disponibilite"

    def lookups(self, request, model_admin):
        return [
            ("available", "Disponible"),
            ("in_cart", "En panier"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "available":
            return queryset.filter(cart=None)
        if self.value() == "in_cart":
            return queryset.exclude(cart=None)
        return queryset


class ArticleAttrAdmin(AdminActionFormsMixin, admin.ModelAdmin):
    list_display = ["id", "name", "shop", "brand_label", "get_status", "get_cart_link"]
    list_filter = ["shop", ArticleAvailabilityFilter]
    search_fields = ["name", "brand_label", "barcode"]
    list_select_related = ["shop", "cart", "cart__shop"]
    ordering = ["shop__name", "name"]

    def get_queryset(self, request):
        """Restrict articles to shops linked to the social worker's center."""
        qs = super().get_queryset(request)
        if request.user.is_staff:
            return qs
        if hasattr(request.user, "socialworker"):
            return qs.filter(shop__social_center=request.user.socialworker.social_center)
        return qs.none()

    @action_with_form(
        ArticleToCartForm,
        description="Assign Article to Cart",
    )
    def assign_to_cart(self, request, queryset, data):
        cart = data["cart"]
        for article in queryset:
            article.cart = cart
            article.save()

    def remove_from_cart(self, request, queryset):
        for article in queryset:
            article.cart = None
            article.save()

    actions = ["assign_to_cart", "remove_from_cart"]

    def get_status(self, obj):
        """Display article status based on cart relationship."""
        if obj.cart is None:
            return mark_safe('<span style="color: green; font-weight: bold;">Disponible</span>')
        cart_status = obj.cart.status
        if cart_status == "COLLECTED":
            return mark_safe('<span style="color: gray; font-weight: bold;">Collecté</span>')
        elif cart_status == "ASSIGNED":
            return mark_safe('<span style="color: orange; font-weight: bold;">Panier assigné</span>')
        else:
            return mark_safe('<span style="color: blue; font-weight: bold;">Panier non assigné</span>')

    get_status.short_description = "Statut"

    def get_cart_link(self, obj):
        """Clickable link to the cart change page, or a dash if not in any cart."""
        if obj.cart is None:
            return "—"
        url = reverse("cart_attrib_admin:api_cart_change", args=[obj.cart.pk])
        return format_html(
            '<a href="{}">Panier #{} ({})</a>',
            url,
            obj.cart.pk,
            obj.cart.status,
        )

    get_cart_link.short_description = "Panier"
    get_cart_link.admin_order_field = "cart__id"

    def has_view_permission(self, request, obj=None):
        """View articles from shops linked to the social worker's center."""
        if not request.user.is_authenticated:
            return False
        return hasattr(request.user, "socialworker") or request.user.is_staff

    def has_module_permission(self, request):
        """Show module for social workers."""
        return request.user.is_authenticated and (hasattr(request.user, "socialworker") or request.user.is_staff)


cart_attrib_admin_site = CartAttributionAdminSite(name="cart_attrib_admin")
cart_attrib_admin_site.register(Recipient, RecipientAttrAdmin)
cart_attrib_admin_site.register(Article, ArticleAttrAdmin)
cart_attrib_admin_site.register(Cart, CartAttribAdmin)

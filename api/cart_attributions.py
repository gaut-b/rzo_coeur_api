from django import forms
from django.contrib import admin
from django.utils.html import format_html
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
        self.base_fields["shop"] = forms.ModelChoiceField(
            queryset=Shop.objects.filter(social_center__name=self.request.user.socialworker.social_center)
        )
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        if not self.request or not (self.request.user.is_staff or hasattr(self.request.user, "socialworker")):
            raise forms.ValidationError("Cannot create cart, insufficient rights.")

        cart = super().save(commit=False)
        cart.shop = self.cleaned_data["shop"]

        if commit:
            cart.save()
        return cart


class CartAttribAdmin(admin.ModelAdmin):
    list_display = ["id", "shop", "status", "collected_at"]

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
        return super().get_form(request, obj, **kwargs)

    # Permissions are to check if user is social worker or superuser
    # add, change, delete and view are reserved to social worker or superuser
    def has_view_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        return hasattr(request.user, "socialworker") or request.user.is_staff

    def has_add_permission(self, request):
        return request.user.is_staff or (
            request.user.is_authenticated
            and hasattr(request.user, "socialworker")
            and request.user.socialworker.is_social_admin
        )

    def has_change_permission(self, request, obj=None):
        if not request.user.is_authenticated:
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
        """Check if user has a social admin role."""
        return user.role == UserRole.SOCIAL_ADMIN.value or user.role == UserRole.SOCIAL_WORKER

    def get_permission_denied_message(self):
        """Custom message for social admin access denied."""
        return "You do not have permission to access the social center admin page."

    pass


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
        return (
            hasattr(request.user, "socialworker")
            and request.user.socialworker.is_social_admin
            and obj.social_center == request.user.socialworker.social_center
            and obj.user != request.user
        )

    # Permissions are to check if social admin
    # add, change, delete and view are reserved to social center admin or superuser
    def has_view_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if obj is None:
            return hasattr(request.user, "socialworker") and request.user.socialworker.is_social_admin
        else:
            return self.is_from_same_social_center(request, obj) or request.user.is_staff

    def has_module_permission(self, request):
        return request.user.is_staff or (
            request.user.is_authenticated
            and hasattr(request.user, "socialworker")
            and request.user.socialworker.is_social_admin
        )


class ArticleToCartForm(ActionForm):
    cart = forms.ModelChoiceField(queryset=Cart.objects.all())

    def clean_cart(self):
        cart = self.cleaned_data["cart"]
        ref_shop = self.queryset.first().shop
        for article in self.queryset:
            if article.shop != ref_shop:
                raise forms.ValidationError("Articles are not from same shop")
        if cart.shop != ref_shop:
            raise forms.ValidationError("Cart and Articles are not from same shop")
        return cart


class ArticleAttrAdmin(AdminActionFormsMixin, admin.ModelAdmin):
    list_display = ["id", "name", "shop", "brand_label", "get_status", "cart"]
    list_filter = ["cart"]

    @action_with_form(
        ArticleToCartForm,
        description="Assign Article to Cart",
    )
    def assign_to_cart(self, request, queryset, data):
        cart = data["cart"]
        for article in queryset:
            article.cart = cart
            article.save()

    @action_with_form(
        ArticleToCartForm,
        description="Remove Article from Cart",
    )
    def remove_from_cart(self, request, queryset, data):
        for article in queryset:
            article.cart = None
            article.save()

    actions = ["assign_to_cart", "remove_from_cart"]

    def get_status(self, obj):
        """Display article status based on cart relationship."""
        if obj.cart is None:
            return format_html('<span style="color: green; font-weight: bold;">Available</span>')

        cart_status = obj.cart.status
        if cart_status == "COLLECTED":
            return format_html('<span style="color: gray;">Collected</span>')
        elif cart_status == "ASSIGNED":
            return format_html('<span style="color: orange;">In Cart (Assigned)</span>')
        else:  # PENDING
            return format_html('<span style="color: blue;">In Cart (Pending)</span>')

    get_status.short_description = "Status"

    def article_from_shop_from_same_social(self, request, obj):
        return (
            hasattr(request.user, "socialworker") and obj.shop.social_center == request.user.socialworker.social_center
        )

    def has_view_permission(self, request, obj=None):
        """View articles from shops that depends from social center."""
        if not request.user.is_authenticated:
            return False
        if obj is None:
            return hasattr(request.user, "socialworker")
        # Check if viewing article from same shop
        return self.article_from_shop_from_same_social(request, obj)

    def has_module_permission(self, request):
        """Show module from shop that depends from social center"""
        return request.user.is_authenticated and hasattr(request.user, "socialworker")


cart_attrib_admin_site = CartAttributionAdminSite(name="car_attrib_admin")
cart_attrib_admin_site.register(Recipient, RecipientAttrAdmin)
cart_attrib_admin_site.register(Article, ArticleAttrAdmin)
cart_attrib_admin_site.register(Cart, CartAttribAdmin)

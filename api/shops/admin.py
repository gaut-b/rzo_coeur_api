import secrets

from django import forms
from django.contrib import admin
from django.utils.html import format_html

from api.admin_sites import (
    AddressLocationAdminForm,
    AddressLocationAdminMixin,
    CustomAdminSite,
)
from api.emails import send_account_welcome_email
from api.models import Article, Cashier, CustomUser, Shop
from api.users.admin import HiddenCustomUserAdmin

# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------


class ShopAdminForm(AddressLocationAdminForm):
    """Custom form for Shop admin."""

    class Meta:
        model = Shop
        fields = [
            "name",
            "social_center",
            "address",
            "postal_code",
            "street_number",
            "street_name",
            "city",
            "latitude",
            "longitude",
        ]


class SocialShopAdminForm(ShopAdminForm):
    """
    Form for SocialShopAdmin when used by a social admin (non-staff).
    Excludes social_center — it is auto-filled from the user's social center
    on save.
    """

    class Meta(ShopAdminForm.Meta):
        fields = [f for f in ShopAdminForm.Meta.fields if f != "social_center"]


# ---------------------------------------------------------------------------
# Shop admin classes (main site + social site)
# ---------------------------------------------------------------------------


class ShopAdmin(AddressLocationAdminMixin, admin.ModelAdmin):
    """
    Standard admin for Shop model (main admin site / superusers).
    Includes address autocomplete and interactive map display.
    No role-specific restrictions — relies on Django's default permissions.
    """

    form = ShopAdminForm
    list_display = [
        "name",
        "full_address",
        "city",
        "postal_code",
        "has_coordinates",
    ]
    list_filter = ["social_center", "city"]
    search_fields = ["name", "street_name", "city", "postal_code"]
    autocomplete_fields = ["social_center"]

    fieldsets = (
        ("General Information", {"fields": ("name", "social_center")}),
        (
            "Address",
            {
                "fields": (
                    "address",
                    "postal_code",
                    "street_number",
                    "street_name",
                    "city",
                    "latitude",
                    "longitude",
                    "display_coordinates",
                ),
                "description": (
                    "Start typing in the address field to see suggestions. "
                    "The structured fields below are auto-filled but can be "
                    "edited."
                ),
            },
        ),
    )

    readonly_fields = ["display_coordinates"]

    class Media:
        css = {
            "all": (
                "api/css/admin_shop.css",
                "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
            )
        }
        js = (
            "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
            "api/js/admin_shop_autocomplete.js",
        )


class SocialShopAdmin(ShopAdmin):
    """
    Restricted admin for Shop model, used in the social admin site.
    Limits visibility and access to shops belonging to the social worker's
    social center.
    """

    autocomplete_fields = ["social_center"]

    def get_form(self, request, obj=None, **kwargs):
        """Use the full ShopAdminForm for staff; stripped form for social admins."""
        if not request.user.is_staff:
            kwargs["form"] = SocialShopAdminForm
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        """Remove social_center from fieldsets for non-staff users."""
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.is_staff:
            return fieldsets
        return tuple(
            (
                name,
                {
                    **options,
                    "fields": tuple(f for f in options["fields"] if f != "social_center"),
                },
            )
            for name, options in fieldsets
        )

    def save_model(self, request, obj, form, change):
        """Auto-assign social_center from the user's profile for non-staff."""
        if not request.user.is_staff and hasattr(request.user, "socialworker"):
            obj.social_center = request.user.socialworker.social_center
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        """
        Return only shops linked to the social worker's social center.
        Staff users see all shops.
        """
        qs = super().get_queryset(request)
        if request.user.is_staff:
            return qs
        if hasattr(request.user, "socialworker"):
            return qs.filter(social_center=request.user.socialworker.social_center)
        return qs.none()

    def _is_from_same_social_center(self, request, obj):
        """Check that obj belongs to the request user's social center."""
        return (
            hasattr(request.user, "socialworker")
            and request.user.socialworker.is_social_admin
            and obj.social_center == request.user.socialworker.social_center
        )

    def has_view_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        if obj is None:
            return hasattr(request.user, "socialworker") and request.user.socialworker.is_social_admin
        return self._is_from_same_social_center(request, obj)

    def has_add_permission(self, request):
        return request.user.is_staff or (
            request.user.is_authenticated
            and hasattr(request.user, "socialworker")
            and request.user.socialworker.is_social_admin
        )

    def has_change_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        if obj is None:
            return hasattr(request.user, "socialworker") and request.user.socialworker.is_social_admin
        return self._is_from_same_social_center(request, obj)

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        if obj is None:
            return hasattr(request.user, "socialworker") and request.user.socialworker.is_social_admin
        return self._is_from_same_social_center(request, obj)

    def has_module_permission(self, request):
        return request.user.is_staff or (
            request.user.is_authenticated
            and hasattr(request.user, "socialworker")
            and request.user.socialworker.is_social_admin
        )


# ---------------------------------------------------------------------------
# Cashier admin (main site)
# ---------------------------------------------------------------------------


class CashierAdmin(admin.ModelAdmin):
    """
    Standard admin for Cashier (for superusers in main admin).
    Allows full control including shop selection.
    """

    list_display = [
        "get_email",
        "get_first_name",
        "get_last_name",
        "shop",
        "is_shop_manager",
    ]
    list_filter = ["is_shop_manager", "shop"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    autocomplete_fields = ["user", "shop"]

    fieldsets = (
        ("User Information", {"fields": ("user",)}),
        ("Shop Assignment", {"fields": ("shop",)}),
        ("Role", {"fields": ("is_shop_manager",)}),
    )

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


# ---------------------------------------------------------------------------
# Shop admin site
# ---------------------------------------------------------------------------


class ShopAdminSite(CustomAdminSite):
    """
    Custom admin site for shop managers and cashiers.
    Accessible at /shop-admin/
    """

    site_header = "Shop Management"
    site_title = "Shop Admin"
    index_title = "Welcome to Shop Administration"

    def check_user_permission(self, user):
        """Check if user has a cashier profile or is staff."""
        return hasattr(user, "cashier") or user.is_staff

    def get_permission_denied_message(self):
        """Custom message for shop admin access denied."""
        return "You do not have permission to access the shop admin."


class CashierCreationForm(forms.ModelForm):
    """
    Custom form for creating cashiers with role selection.
    The shop field is automatically filled from the logged-in manager's shop.
    """

    email = forms.EmailField(required=True, help_text="Email address for the new user")
    first_name = forms.CharField(required=True, max_length=150)
    last_name = forms.CharField(required=True, max_length=150)
    role = forms.TypedChoiceField(
        choices=[
            (True, "Shop Manager"),
            (False, "Cashier"),
        ],
        coerce=lambda x: x == "True",
        required=True,
        help_text="Select role for this user",
    )

    class Meta:
        model = Cashier
        fields = ["email", "first_name", "last_name", "role"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        if not self.request or not hasattr(self.request.user, "cashier"):
            raise forms.ValidationError("Unable to determine shop. You must be logged in as a shop manager.")

        generated_password = secrets.token_urlsafe(20)
        user = CustomUser.objects.create_user(
            email=self.cleaned_data["email"],
            password=generated_password,
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
        )

        cashier = super().save(commit=False)
        cashier.user = user
        cashier.shop = self.request.user.cashier.shop
        cashier.is_shop_manager = self.cleaned_data["role"]

        if commit:
            cashier.save()

        send_account_welcome_email(
            user,
            callback_url="/shop-admin/login/",
            request=self.request,
        )
        return cashier


class CashierShopAdmin(admin.ModelAdmin):
    """
    Admin for managing cashiers in the shop.
    Only accessible to shop managers.
    """

    list_display = [
        "get_email",
        "get_first_name",
        "get_last_name",
        "get_role",
        "shop",
    ]
    list_filter = ["is_shop_manager", "shop"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    autocomplete_fields = ["user"]

    fieldsets = (
        ("User Information", {"fields": ("user",)}),
        ("Role", {"fields": ("is_shop_manager",)}),
    )

    add_fieldsets = (
        (
            "User Information",
            {"fields": ("email", "first_name", "last_name")},
        ),
        (
            "Role",
            {
                "fields": ("role",),
                "description": ("Select whether this user should be a regular cashier or a shop manager."),
            },
        ),
    )

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

    def get_role(self, obj):
        return "Manager" if obj.is_shop_manager else "Cashier"

    get_role.short_description = "Role"

    def get_fieldsets(self, request, obj=None):
        """Use different fieldsets for creation vs editing."""
        if obj is None:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        """Use custom form for creation, standard form for editing."""
        if obj is None:
            kwargs["form"] = CashierCreationForm
            form_class = super().get_form(request, obj, **kwargs)

            class FormWithRequest(form_class):
                def __init__(self, *args, **form_kwargs):
                    form_kwargs["request"] = request
                    super().__init__(*args, **form_kwargs)

            return FormWithRequest
        return super().get_form(request, obj, **kwargs)

    def get_queryset(self, request):
        """Filter cashiers by the logged-in user's shop. Staff see all."""
        qs = super().get_queryset(request)
        if request.user.is_staff:
            return qs
        if hasattr(request.user, "cashier"):
            return qs.filter(shop=request.user.cashier.shop)
        return qs.none()

    def has_view_permission(self, request, obj=None):
        """Shop managers and staff can view cashiers."""
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        if obj is None:
            return hasattr(request.user, "cashier") and request.user.cashier.is_shop_manager
        return (
            hasattr(request.user, "cashier")
            and request.user.cashier.is_shop_manager
            and obj.shop == request.user.cashier.shop
        )

    def has_add_permission(self, request):
        """Shop managers and staff can add cashiers."""
        return request.user.is_staff or (
            request.user.is_authenticated and hasattr(request.user, "cashier") and request.user.cashier.is_shop_manager
        )

    def has_change_permission(self, request, obj=None):
        """Shop managers and staff can edit cashiers."""
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        if obj is None:
            return hasattr(request.user, "cashier") and request.user.cashier.is_shop_manager
        return (
            hasattr(request.user, "cashier")
            and request.user.cashier.is_shop_manager
            and obj.shop == request.user.cashier.shop
        )

    def has_delete_permission(self, request, obj=None):
        """Shop managers and staff can delete cashiers."""
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        if obj is None:
            return hasattr(request.user, "cashier") and request.user.cashier.is_shop_manager
        return (
            hasattr(request.user, "cashier")
            and request.user.cashier.is_shop_manager
            and obj.shop == request.user.cashier.shop
            and obj.user != request.user
        )

    def has_module_permission(self, request):
        """Show module to shop managers and staff."""
        return request.user.is_staff or (
            request.user.is_authenticated and hasattr(request.user, "cashier") and request.user.cashier.is_shop_manager
        )


class ArticleShopAdmin(admin.ModelAdmin):
    """
    Read-only admin for viewing articles in the shop.
    Accessible to both cashiers and shop managers.
    """

    list_display = [
        "id",
        "name",
        "barcode",
        "brand_label",
        "get_status",
        "created_at",
    ]
    list_filter = ["created_at", "cart"]
    search_fields = ["barcode", "brand_label", "name"]
    readonly_fields = [
        "name",
        "barcode",
        "brand_label",
        "client",
        "shop",
        "cart",
        "img_url",
        "thumb_url",
        "created_at",
        "updated_at",
        "get_status",
    ]

    fieldsets = [
        (
            "Article Information",
            {"fields": ["name", "barcode", "brand_label", "get_status"]},
        ),
        (
            "Images",
            {"fields": ["img_url", "thumb_url"]},
        ),
        (
            "Relationships",
            {"fields": ["client", "shop", "cart"]},
        ),
        (
            "Timestamps",
            {"fields": ["created_at", "updated_at"]},
        ),
    ]

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

    def get_queryset(self, request):
        """Filter articles by the logged-in user's shop. Staff see all."""
        qs = super().get_queryset(request)
        if request.user.is_staff:
            return qs
        if hasattr(request.user, "cashier"):
            return qs.filter(shop=request.user.cashier.shop)
        return qs.none()

    def has_add_permission(self, request):
        """No one can add articles through shop admin (done via mobile app)."""
        return False

    def has_change_permission(self, request, obj=None):
        """No one can edit articles through shop admin (read-only)."""
        return False

    def has_delete_permission(self, request, obj=None):
        """No one can delete articles through shop admin."""
        return False

    def has_view_permission(self, request, obj=None):
        """Cashiers, managers and staff can view articles."""
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        if obj is None:
            return hasattr(request.user, "cashier")
        return hasattr(request.user, "cashier") and obj.shop == request.user.cashier.shop

    def has_module_permission(self, request):
        """Show module to shop users and staff."""
        return request.user.is_staff or (request.user.is_authenticated and hasattr(request.user, "cashier"))


# ---------------------------------------------------------------------------
# Register models on main admin site
# ---------------------------------------------------------------------------

admin.site.register(Shop, ShopAdmin)
admin.site.register(Cashier, CashierAdmin)

# ---------------------------------------------------------------------------
# Shop admin site instance
# ---------------------------------------------------------------------------

shop_admin_site = ShopAdminSite(name="shop_admin")
shop_admin_site.register(CustomUser, HiddenCustomUserAdmin)
shop_admin_site.register(Article, ArticleShopAdmin)
shop_admin_site.register(Cashier, CashierShopAdmin)

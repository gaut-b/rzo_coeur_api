from django import forms
from django.contrib import admin
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth.admin import UserAdmin
from django.contrib.gis.geos import Point
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache

from .enums import UserRole
from .models import (
    Article,
    Cart,
    Cashier,
    Client,
    CustomUser,
    Recipient,
    Shop,
    SocialCenter,
    SocialWorker,
)


# Register your models here.
class AddressLocationAdminForm(forms.ModelForm):
    """Base form for models with address and location fields."""

    address = forms.CharField(
        required=False,
        max_length=200,
        help_text="Start typing to search for an address",
        widget=forms.TextInput(attrs={"placeholder": "Search address..."}),
    )

    # Virtual fields for latitude/longitude
    latitude = forms.DecimalField(
        required=False,
        max_digits=9,
        decimal_places=6,
        widget=forms.NumberInput(attrs={"step": "0.000001"}),
    )
    longitude = forms.DecimalField(
        required=False,
        max_digits=9,
        decimal_places=6,
        widget=forms.NumberInput(attrs={"step": "0.000001"}),
    )

    class Meta:
        fields = [
            "address",
            "postal_code",
            "street_number",
            "street_name",
            "city",
            "latitude",
            "longitude",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance or not self.instance.pk:
            return
        # Pre-fill the address field with current structured address
        address_parts = filter(None, [self.instance.street_number, self.instance.street_name])
        address_line = " ".join(address_parts)

        if self.instance.postal_code and self.instance.city:
            if address_line:
                self.initial["address"] = f"{address_line}, {self.instance.postal_code} {self.instance.city}"
            else:
                self.initial["address"] = f"{self.instance.postal_code} {self.instance.city}"
        elif address_line:
            self.initial["address"] = address_line

        # Pre-fill latitude/longitude from location Point
        if self.instance.location:
            self.initial["latitude"] = self.instance.location.y
            self.initial["longitude"] = self.instance.location.x

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Create Point from latitude/longitude if both are provided
        latitude = self.cleaned_data.get("latitude")
        longitude = self.cleaned_data.get("longitude")

        if latitude is not None and longitude is not None:
            instance.location = Point(float(longitude), float(latitude), srid=4326)

        if commit:
            instance.save()
        return instance


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


class SocialCenterAdminForm(AddressLocationAdminForm):
    """Custom form for SocialCenter admin."""

    class Meta:
        model = SocialCenter
        fields = [
            "name",
            "mail",
            "address",
            "postal_code",
            "street_number",
            "street_name",
            "city",
            "latitude",
            "longitude",
        ]


class AddressLocationAdminMixin:
    """Mixin for admin classes with address and location display methods."""

    def full_address(self, obj):
        """Display the full address constructed from structured fields."""
        parts = []
        if obj.street_number:
            parts.append(obj.street_number)
        if obj.street_name:
            parts.append(obj.street_name)
        address_line = " ".join(parts) if parts else ""

        if obj.postal_code and obj.city:
            if address_line:
                return f"{address_line}, {obj.postal_code} {obj.city}"
            return f"{obj.postal_code} {obj.city}"
        elif address_line:
            return address_line
        return "-"

    full_address.short_description = "Address"

    def has_coordinates(self, obj, *args, **kwargs):
        """Display whether the object has GPS coordinates."""
        if obj.latitude and obj.longitude:
            return format_html('<span style="color: green;">✓</span>', *args, **kwargs)
        return format_html('<span style="color: red;">✗</span>', *args, **kwargs)

    has_coordinates.short_description = "GPS"

    def display_coordinates(self, obj, *args, **kwargs):
        """Display GPS coordinates in a readable format."""
        if obj.latitude and obj.longitude:
            return format_html(
                "<strong>Latitude:</strong> {}<br><strong>Longitude:</strong> {}",
                obj.latitude,
                obj.longitude,
            )
        return "No GPS coordinates"

    display_coordinates.short_description = "GPS Coordinates"


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ["email", "first_name", "last_name", "is_staff", "is_active"]
    list_filter = ["is_staff", "is_active"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "first_name",
                    "last_name",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["email"]


class ShopAdmin(AddressLocationAdminMixin, admin.ModelAdmin):
    """
    Custom admin for Shop model with address autocomplete
    and interactive map display.
    """

    form = ShopAdminForm
    list_display = ["name", "full_address", "city", "postal_code", "has_coordinates"]
    list_filter = ["social_center", "city"]
    search_fields = ["name", "street_name", "city", "postal_code"]

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
                    "The structured fields below are auto-filled but can be edited."
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

    # Make sure we are only seeing the related shops whether user is social admin or superuser
    def get_queryset(self, request):
        if hasattr(request.user, "socialworker") and request.user.socialworker.is_social_admin:
            request_social_center = "0"
            qs = super(ShopAdmin, self).get_queryset(request)
            for s in Shop.objects.all():
                if hasattr(request.user, "socialworker"):  # we're not going through this...FIXME
                    request_social_center = request.user.socialworker.social_center
            return qs.filter(social_center=request_social_center)
        else:
            return super(ShopAdmin, self).get_queryset(request)

    def is_from_same_social_center(self, request, obj):
        return (
            hasattr(request.user, "socialworker")
            and request.user.socialworker.is_social_admin
            and obj.social_center == request.user.socialworker.social_center
        )

    def has_view_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if obj is None:
            print(f"{Shop.objects.all()}")
            return hasattr(request.user, "socialworker") and request.user.socialworker.is_social_admin
        else:
            return self.is_from_same_social_center(request, obj) or request.user.is_staff

    def has_add_permission(self, request):
        return request.user.is_staff or (
            request.user.is_authenticated
            and hasattr(request.user, "socialworker")
            and request.user.socialworker.is_social_admin
        )

    def has_change_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if obj is None:
            return request.user.is_staff or (
                hasattr(request.user, "socialworker") and request.user.socialworker.is_social_admin
            )
        else:
            return self.is_from_same_social_center(request, obj) or request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if obj is None:
            return request.user.is_staff or (
                hasattr(request.user, "socialworker") and request.user.socialworker.is_social_admin
            )
        else:
            return self.is_from_same_social_center(request, obj) or request.user.is_staff

    def has_module_permission(self, request):
        return request.user.is_staff or (
            request.user.is_authenticated
            and hasattr(request.user, "socialworker")
            and request.user.socialworker.is_social_admin
        )


class SocialCenterAdmin(AddressLocationAdminMixin, admin.ModelAdmin):
    """
    Custom admin for SocialCenter model with address autocomplete
    and interactive map display.
    """

    form = SocialCenterAdminForm
    list_display = ["name", "mail", "full_address", "city", "postal_code", "has_coordinates"]
    list_filter = ["city"]
    search_fields = ["name", "street_name", "city", "postal_code", "mail"]

    fieldsets = (
        ("General Information", {"fields": ("name", "mail")}),
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
                    "The structured fields below are auto-filled but can be edited."
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


class CashierAdmin(admin.ModelAdmin):
    """
    Standard admin for Cashier (for superusers in main admin).
    Allows full control including shop selection.
    """

    list_display = ["get_email", "get_first_name", "get_last_name", "shop", "is_shop_manager"]
    list_filter = ["is_shop_manager", "shop"]
    search_fields = ["user__email", "user__first_name", "user__last_name", "shop__name"]
    raw_id_fields = ["user"]

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


admin.site.register(Shop, ShopAdmin)
admin.site.register(SocialCenter, SocialCenterAdmin)
admin.site.register(SocialWorker)
admin.site.register(Cashier, CashierAdmin)
admin.site.register(Client)
admin.site.register(CustomUser, CustomUserAdmin)


class CartAdmin(admin.ModelAdmin):
    readonly_fields = ["status"]
    list_display = ["id", "shop", "recipient", "status", "collected_at"]
    list_filter = ["shop", "collected_at"]
    search_fields = ["id", "shop__name", "recipient__user__email"]


admin.site.register(Cart, CartAdmin)


class ArticleAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "barcode", "brand_label", "client", "shop", "cart", "created_at"]
    list_filter = ["shop", "created_at", "cart"]
    search_fields = ["barcode", "brand_label", "name", "client__user__email"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        (
            "Article Information",
            {
                "fields": ["name", "barcode", "brand_label"],
            },
        ),
        (
            "Images",
            {
                "fields": ["img_url", "thumb_url"],
            },
        ),
        (
            "Relationships",
            {
                "fields": ["client", "shop", "cart"],
            },
        ),
        (
            "Timestamps",
            {
                "fields": ["created_at", "updated_at"],
            },
        ),
    ]


admin.site.register(Article, ArticleAdmin)


# ============================================
# BASE CUSTOM ADMIN SITE (reusable for different admin interfaces)
# ============================================


class CustomAdminSite(admin.AdminSite):
    """
    Base custom admin site with reusable login logic that doesn't require is_staff.
    Subclasses must implement check_user_permission() to define role-specific access.
    """

    login_template = "admin/custom_admin_login.html"

    def check_user_permission(self, user):
        """
        Check if user has permission to access this admin site.
        Must be implemented by subclasses.

        Returns:
            bool: True if user has permission, False otherwise
        """
        raise NotImplementedError("Subclasses must implement check_user_permission()")

    def get_permission_denied_message(self):
        """
        Get the error message to display when user doesn't have permission.
        Can be overridden by subclasses for custom messages.
        """
        return "You do not have permission to access this area."

    @method_decorator(never_cache)
    def login(self, request, extra_context=None):
        """
        Custom login that doesn't require is_staff.
        Displays the login form and handles the login action.
        """
        if request.method == "POST":
            username = request.POST.get("username")
            password = request.POST.get("password")

            # Authenticate user
            user = authenticate(request, username=username, password=password)

            if user is not None and user.is_active:
                # Check if user has the required role
                if self.check_user_permission(user):
                    auth_login(request, user)
                    # Validate and redirect to the page they were trying to access or index
                    next_url = request.GET.get("next", request.POST.get("next", ""))
                    if next_url and url_has_allowed_host_and_scheme(
                        url=next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
                    ):
                        return redirect(next_url)
                    else:
                        return redirect(reverse("admin:index", current_app=self.name))
                else:
                    # User doesn't have the required role
                    context = {
                        "title": f"{self.site_title} Login",
                        "site_title": self.site_title,
                        "site_header": self.site_header,
                        "error_message": self.get_permission_denied_message(),
                        "username": username,
                    }
                    return render(request, self.login_template, context)
            else:
                # Invalid credentials
                context = {
                    "title": f"{self.site_title} Login",
                    "site_title": self.site_title,
                    "site_header": self.site_header,
                    "error_message": "Please enter a correct email and password.",
                    "username": username,
                }
                return render(request, self.login_template, context)

        # GET request - show login form
        context = {
            "title": f"{self.site_title} Login",
            "site_title": self.site_title,
            "site_header": self.site_header,
            "site": self,
            "next": request.GET.get("next", ""),
        }
        if extra_context:
            context.update(extra_context)

        return render(request, self.login_template, context)

    def has_permission(self, request):
        """
        Allow access to users who pass the role-specific check.
        Does NOT require is_staff=True.
        """
        return request.user.is_active and request.user.is_authenticated and self.check_user_permission(request.user)


# ============================================
# SOCIAL ADMIN SITE (SOCIAL CENTER ADMIN)
# ============================================


class SocialAdminSite(CustomAdminSite):
    site_header = "Social Center Admin"
    site_title = "Social Center"
    index_title = "Welcome to social center interface"

    def check_user_permission(self, user):
        """Check if user has a social admin role."""
        return user.role == UserRole.SOCIAL_ADMIN.value or user.is_staff

    def get_permission_denied_message(self):
        """Custom message for social admin access denied."""
        return "You do not have permission to access the social center admin page."


class SocialWorkerCreationForm(forms.ModelForm):
    """
    Custom form for creating social worker.
    The social center field is automatically filled from the logged-in admin's social center.
    """

    email = forms.EmailField(required=True, help_text="Email address for the new user")
    first_name = forms.CharField(required=True, max_length=150)
    last_name = forms.CharField(required=True, max_length=150)
    password = forms.CharField(widget=forms.PasswordInput, required=True, help_text="Password for the new user")

    class Meta:
        model = SocialWorker
        fields = ["email", "first_name", "last_name", "password"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        # Don't show shop field - it will be auto-filled

    def save(self, commit=True):
        # Validate that we can determine the shop
        if not self.request or not hasattr(self.request.user, "socialworker"):
            raise forms.ValidationError("Cannot create user, insufficient rights.")

        # Create the CustomUser first
        user = CustomUser.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
        )

        # Create the SocialWorker instance
        socialworker = super().save(commit=False)
        socialworker.user = user
        if self.request.user.socialworker:
            socialworker.social_center = self.request.user.socialworker.social_center

        # social admin is created by superuser
        socialworker.is_social_admin = False

        if commit:
            socialworker.save()
        return socialworker


class RecipientCreationForm(forms.ModelForm):
    """
    Custom form for creating Recipient.
    The social center field is automatically filled from the logged-in admin's social center.
    """

    email = forms.EmailField(required=True, help_text="Email address for the new user")
    first_name = forms.CharField(required=True, max_length=150)
    last_name = forms.CharField(required=True, max_length=150)
    password = forms.CharField(widget=forms.PasswordInput, required=True, help_text="Password for the new user")

    class Meta:
        model = Recipient
        fields = ["email", "first_name", "last_name", "password"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        # Don't show shop field - it will be auto-filled

    def save(self, commit=True):
        if not self.request or not (self.request.user.is_staff or hasattr(self.request.user, "socialworker")):
            raise forms.ValidationError("Cannot create user, insufficient rights.")

        # Create the CustomUser first
        user = CustomUser.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
        )

        # Create the Recipient instance
        recipient = super().save(commit=False)
        recipient.user = user
        if hasattr(self.request.user, "socialworker"):
            recipient.social_center = self.request.user.socialworker.social_center

        if commit:
            recipient.save()
        return recipient


class SocialWorkerAdmin(admin.ModelAdmin):
    """
    Admin for managing social workers in the social_center.
    Only accessible to social admin.
    """

    list_display = ["get_email", "get_first_name", "get_last_name", "social_center"]
    list_filter = ["is_social_admin", "social_center"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]

    # Fieldsets for editing existing cashiers
    fieldsets = (
        ("User Information", {"fields": ("user",)}),
        ("Role", {"fields": ("is_social_admin",)}),
    )

    # Fieldsets for creating new cashiers
    add_fieldsets = (
        (
            "User Information",
            {
                "fields": ("email", "first_name", "last_name", "password"),
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

    def get_fieldsets(self, request, obj=None):
        """Use different fieldsets for creation vs editing."""
        if obj is None:  # Creating new social worker
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        """Use custom form for creation, standard form for editing."""
        if obj is None:  # Creating new social worker
            kwargs["form"] = SocialWorkerCreationForm
            form_class = super().get_form(request, obj, **kwargs)

            # Create a wrapper that injects request into form instantiation
            class FormWithRequest(form_class):
                def __init__(self, *args, **form_kwargs):
                    form_kwargs["request"] = request
                    super().__init__(*args, **form_kwargs)

            return FormWithRequest
        return super().get_form(request, obj, **kwargs)

    def get_queryset(self, request):
        """Filter social workers by the logged-in user's social center."""
        qs = super().get_queryset(request)
        if hasattr(request.user, "socialworker"):
            return qs.filter(social_center=request.user.socialworker.social_center)
        return qs.none()

    def is_from_same_social_center(self, request, obj):
        return (
            hasattr(request.user, "socialworker")
            and request.user.socialworker.is_social_admin
            and obj.social_center == request.user.socialworker.social_center
            and obj.user != request.user
        )

    # Permissions are to check if social admin
    #  view, add, change, delete needs the is_social_admin field or superuser status

    def has_view_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if obj is None:
            return (
                hasattr(request.user, "socialworker")
                and request.user.socialworker.is_social_admin
                or request.user.is_staff
            )
        else:
            return self.is_from_same_social_center(request, obj) or request.user.is_staff

    def has_add_permission(self, request):
        return (
            request.user.is_authenticated
            and hasattr(request.user, "socialworker")
            and request.user.socialworker.is_social_admin
            or request.user.is_staff
        )

    def has_change_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if obj is None:
            return (
                hasattr(request.user, "socialworker")
                and request.user.socialworker.is_social_admin
                or request.user.is_staff
            )
        else:
            return self.is_from_same_social_center(request, obj) or request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if obj is None:
            return (
                hasattr(request.user, "socialworker")
                and request.user.socialworker.is_social_admin
                or request.user.is_staff
            )
        else:
            return self.is_from_same_social_center(request, obj) or request.user.is_staff

    def has_module_permission(self, request):
        return (
            request.user.is_authenticated
            and hasattr(request.user, "socialworker")
            and request.user.socialworker.is_social_admin
            or request.user.is_staff
        )


class RecipientAdmin(admin.ModelAdmin):
    list_display = ["get_email", "get_first_name", "get_last_name", "social_center"]
    list_filter = ["social_center"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]

    # Fieldsets for editing existing cashiers
    fieldsets = (("User Information", {"fields": ("user",)}),)

    # Fieldsets for creating new cashiers
    add_fieldsets = (
        (
            "User Information",
            {
                "fields": ("email", "first_name", "last_name", "password"),
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

    def get_fieldsets(self, request, obj=None):
        """Use different fieldsets for creation vs editing."""
        if obj is None:  # Creating new Recipient
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        """Use custom form for creation, standard form for editing."""
        if obj is None:  # Creating new Recipient
            kwargs["form"] = RecipientCreationForm
            form_class = super().get_form(request, obj, **kwargs)

            # Create a wrapper that injects request into form instantiation
            class FormWithRequest(form_class):
                def __init__(self, *args, **form_kwargs):
                    form_kwargs["request"] = request
                    super().__init__(*args, **form_kwargs)

            return FormWithRequest
        return super().get_form(request, obj, **kwargs)

    def get_queryset(self, request):
        """Filter social workers by the logged-in user's social center."""
        qs = super().get_queryset(request)
        if hasattr(request.user, "socialworker"):
            return qs.filter(social_center=request.user.socialworker.social_center)
        return qs.none()

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

    def has_add_permission(self, request):
        return request.user.is_staff or (
            request.user.is_authenticated
            and hasattr(request.user, "socialworker")
            and request.user.socialworker.is_social_admin
        )

    def has_change_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if obj is None:
            return request.user.is_staff or (
                hasattr(request.user, "socialworker") and request.user.socialworker.is_social_admin
            )
        else:
            return self.is_from_same_social_center(request, obj) or request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if obj is None:
            return request.user.is_staff or (
                hasattr(request.user, "socialworker") and request.user.socialworker.is_social_admin
            )
        else:
            return self.is_from_same_social_center(request, obj) or request.user.is_staff

    def has_module_permission(self, request):
        return request.user.is_staff or (
            request.user.is_authenticated
            and hasattr(request.user, "socialworker")
            and request.user.socialworker.is_social_admin
        )


social_admin_site = SocialAdminSite(name="social_admin")
social_admin_site.register(Shop, ShopAdmin)
social_admin_site.register(SocialWorker, SocialWorkerAdmin)
social_admin_site.register(Recipient, RecipientAdmin)
admin.site.register(Recipient, RecipientAdmin)

# ============================================
# SHOP ADMIN SITE (for Cashiers and Managers)
# ============================================


class ShopAdminSite(CustomAdminSite):
    """
    Custom admin site for shop managers and cashiers.
    Accessible at /shop-admin/
    """

    site_header = "Shop Management"
    site_title = "Shop Admin"
    index_title = "Welcome to Shop Administration"

    def check_user_permission(self, user):
        """Check if user has a cashier profile."""
        return hasattr(user, "cashier")

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
    password = forms.CharField(widget=forms.PasswordInput, required=True, help_text="Password for the new user")
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
        fields = ["email", "first_name", "last_name", "password", "role"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        # Don't show shop field - it will be auto-filled

    def save(self, commit=True):
        if not self.request or not hasattr(self.request.user, "cashier"):
            raise forms.ValidationError("Unable to determine shop. You must be logged in as a shop manager.")

        # Create the CustomUser first
        user = CustomUser.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
        )

        # Create the Cashier instance
        cashier = super().save(commit=False)
        cashier.user = user
        cashier.shop = self.request.user.cashier.shop

        # Set is_shop_manager based on role selection
        cashier.is_shop_manager = self.cleaned_data["role"]

        if commit:
            cashier.save()
        return cashier


class CashierShopAdmin(admin.ModelAdmin):
    """
    Admin for managing cashiers in the shop.
    Only accessible to shop managers.
    """

    list_display = ["get_email", "get_first_name", "get_last_name", "get_role", "shop"]
    list_filter = ["is_shop_manager", "shop"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]

    # Fieldsets for editing existing cashiers
    fieldsets = (
        ("User Information", {"fields": ("user",)}),
        ("Role", {"fields": ("is_shop_manager",)}),
    )

    # Fieldsets for creating new cashiers
    add_fieldsets = (
        (
            "User Information",
            {
                "fields": ("email", "first_name", "last_name", "password"),
            },
        ),
        (
            "Role",
            {
                "fields": ("role",),
                "description": "Select whether this user should be a regular cashier or a shop manager.",
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
        if obj is None:  # Creating new cashier
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        """Use custom form for creation, standard form for editing."""
        if obj is None:  # Creating new cashier
            kwargs["form"] = CashierCreationForm
            form_class = super().get_form(request, obj, **kwargs)

            # Create a wrapper that injects request into form instantiation
            class FormWithRequest(form_class):
                def __init__(self, *args, **form_kwargs):
                    form_kwargs["request"] = request
                    super().__init__(*args, **form_kwargs)

            return FormWithRequest
        return super().get_form(request, obj, **kwargs)

    def get_queryset(self, request):
        """Filter cashiers by the logged-in user's shop."""
        qs = super().get_queryset(request)
        if hasattr(request.user, "cashier"):
            return qs.filter(shop=request.user.cashier.shop)
        return qs.none()

    def has_view_permission(self, request, obj=None):
        """Only shop managers can view cashiers."""
        if not request.user.is_authenticated:
            return False
        if obj is None:
            return hasattr(request.user, "cashier") and request.user.cashier.is_shop_manager
        # Check if viewing cashier from same shop
        return (
            hasattr(request.user, "cashier")
            and request.user.cashier.is_shop_manager
            and obj.shop == request.user.cashier.shop
        )

    def has_add_permission(self, request):
        """Only shop managers can add cashiers."""
        return (
            request.user.is_authenticated and hasattr(request.user, "cashier") and request.user.cashier.is_shop_manager
        )

    def has_change_permission(self, request, obj=None):
        """Only shop managers can edit cashiers (including themselves)."""
        if not request.user.is_authenticated:
            return False
        if obj is None:
            return hasattr(request.user, "cashier") and request.user.cashier.is_shop_manager
        # Check if editing cashier from same shop
        return (
            hasattr(request.user, "cashier")
            and request.user.cashier.is_shop_manager
            and obj.shop == request.user.cashier.shop
        )

    def has_delete_permission(self, request, obj=None):
        """Only shop managers can delete cashiers."""
        if not request.user.is_authenticated:
            return False
        if obj is None:
            return hasattr(request.user, "cashier") and request.user.cashier.is_shop_manager
        # Prevent deleting yourself and check same shop
        return (
            hasattr(request.user, "cashier")
            and request.user.cashier.is_shop_manager
            and obj.shop == request.user.cashier.shop
            and obj.user != request.user
        )

    def has_module_permission(self, request):
        """Show module only to shop managers."""
        return (
            request.user.is_authenticated and hasattr(request.user, "cashier") and request.user.cashier.is_shop_manager
        )


class ArticleShopAdmin(admin.ModelAdmin):
    """
    Read-only admin for viewing articles in the shop.
    Accessible to both cashiers and shop managers.
    """

    list_display = ["id", "name", "barcode", "brand_label", "get_status", "created_at"]
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
            {
                "fields": ["name", "barcode", "brand_label", "get_status"],
            },
        ),
        (
            "Images",
            {
                "fields": ["img_url", "thumb_url"],
            },
        ),
        (
            "Relationships",
            {
                "fields": ["client", "shop", "cart"],
            },
        ),
        (
            "Timestamps",
            {
                "fields": ["created_at", "updated_at"],
            },
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
        """Filter articles by the logged-in user's shop."""
        qs = super().get_queryset(request)
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
        """Both cashiers and managers can view articles."""
        if not request.user.is_authenticated:
            return False
        if obj is None:
            return hasattr(request.user, "cashier")
        # Check if viewing article from same shop
        return hasattr(request.user, "cashier") and obj.shop == request.user.cashier.shop

    def has_module_permission(self, request):
        """Show module to all shop users (cashiers and managers)."""
        return request.user.is_authenticated and hasattr(request.user, "cashier")


# Create shop admin site instance
shop_admin_site = ShopAdminSite(name="shop_admin")
shop_admin_site.register(Article, ArticleShopAdmin)
shop_admin_site.register(Cashier, CashierShopAdmin)

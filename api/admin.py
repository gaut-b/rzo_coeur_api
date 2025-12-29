from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.gis.geos import Point
from django.utils.html import format_html

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
                self.initial["address"] = (
                    f"{address_line}, {self.instance.postal_code} {self.instance.city}"
                )
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
        elif latitude is None and longitude is None:
            # Only clear location if both fields are explicitly None
            instance.location = None
        # Otherwise, keep existing location unchanged

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


admin.site.register(Shop, ShopAdmin)
admin.site.register(SocialCenter, SocialCenterAdmin)
admin.site.register(SocialWorker)
admin.site.register(Cashier)
admin.site.register(Recipient)
admin.site.register(Client)
admin.site.register(CustomUser, CustomUserAdmin)


class CartAdmin(admin.ModelAdmin):
    readonly_fields = ["status"]
    list_display = ["id", "shop", "recipient", "status", "collected_at"]
    list_filter = ["shop", "collected_at"]
    search_fields = ["id", "shop__name", "recipient__user__email"]


admin.site.register(Cart, CartAdmin)
admin.site.register(Article)

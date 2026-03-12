from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from api.models import Client, CustomUser


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


class ClientAdmin(admin.ModelAdmin):
    """Standard admin for Client model (main admin site / superusers)."""

    list_display = ["get_email", "get_first_name", "get_last_name"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    autocomplete_fields = ["user"]

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


class HiddenCustomUserAdmin(admin.ModelAdmin):
    """
    Minimal CustomUser admin registered on sub-sites solely to enable
    autocomplete_fields on models that reference CustomUser.
    Hidden from the navigation (has_module_permission returns False).
    """

    search_fields = ["email", "first_name", "last_name"]

    def has_view_permission(self, request, obj=None):
        return request.user.is_authenticated and (
            request.user.is_staff or hasattr(request.user, "socialworker") or hasattr(request.user, "cashier")
        )

    def has_module_permission(self, request):
        return False


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Client, ClientAdmin)

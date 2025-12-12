from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

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


admin.site.register(Shop)
admin.site.register(SocialCenter)
admin.site.register(SocialWorker)
admin.site.register(Cashier)
admin.site.register(Recipient)
admin.site.register(Client)
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Cart)
admin.site.register(Article)

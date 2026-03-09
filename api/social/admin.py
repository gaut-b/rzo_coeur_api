import secrets

from django import forms
from django.conf import settings
from django.contrib import admin

from api.admin_sites import (
    AddressLocationAdminForm,
    AddressLocationAdminMixin,
    CustomAdminSite,
)
from api.emails import send_account_welcome_email
from api.enums import UserRole
from api.models import CustomUser, Recipient, Shop, SocialCenter, SocialWorker
from api.shops.admin import SocialShopAdmin
from api.users.admin import HiddenCustomUserAdmin

# ---------------------------------------------------------------------------
# Admin forms
# ---------------------------------------------------------------------------


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


class SocialWorkerCreationForm(forms.ModelForm):
    """
    Custom form for creating a social worker.
    Used by social admins — social_center is auto-filled from the user's
    own social center on save.
    """

    email = forms.EmailField(required=True, help_text="Email address for the new user")
    first_name = forms.CharField(required=True, max_length=150)
    last_name = forms.CharField(required=True, max_length=150)

    class Meta:
        model = SocialWorker
        fields = ["email", "first_name", "last_name"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        if not self.request or not hasattr(self.request.user, "socialworker"):
            raise forms.ValidationError("Cannot create user, insufficient rights.")

        generated_password = secrets.token_urlsafe(20)
        user = CustomUser.objects.create_user(
            email=self.cleaned_data["email"],
            password=generated_password,
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
        )

        socialworker = super().save(commit=False)
        socialworker.user = user
        if self.request.user.socialworker:
            socialworker.social_center = self.request.user.socialworker.social_center
        socialworker.is_social_admin = False

        if commit:
            socialworker.save()

        send_account_welcome_email(
            user,
            login_url="/social-admin/login/",
            request=self.request,
        )
        return socialworker


class SocialWorkerStaffCreationForm(forms.ModelForm):
    """
    Custom form for creating a social worker, used by staff.
    Exposes social_center as a selectable field.
    """

    email = forms.EmailField(required=True, help_text="Email address for the new user")
    first_name = forms.CharField(required=True, max_length=150)
    last_name = forms.CharField(required=True, max_length=150)

    class Meta:
        model = SocialWorker
        fields = [
            "email",
            "first_name",
            "last_name",
            "social_center",
        ]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        """Create the linked CustomUser then the SocialWorker."""
        generated_password = secrets.token_urlsafe(20)
        user = CustomUser.objects.create_user(
            email=self.cleaned_data["email"],
            password=generated_password,
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
        )

        socialworker = super().save(commit=False)
        socialworker.user = user
        socialworker.is_social_admin = False

        if commit:
            socialworker.save()

        send_account_welcome_email(
            user,
            login_url="/social-admin/login/",
            request=self.request,
        )
        return socialworker


class RecipientCreationForm(forms.ModelForm):
    """
    Custom form for creating a Recipient.
    Used by social admins — social_center is auto-filled from the user's
    own social center on save.
    """

    email = forms.EmailField(required=True, help_text="Email address for the new user")
    first_name = forms.CharField(required=True, max_length=150)
    last_name = forms.CharField(required=True, max_length=150)

    class Meta:
        model = Recipient
        fields = ["email", "first_name", "last_name"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        if not self.request or not (self.request.user.is_staff or hasattr(self.request.user, "socialworker")):
            raise forms.ValidationError("Cannot create user, insufficient rights.")

        generated_password = secrets.token_urlsafe(20)
        user = CustomUser.objects.create_user(
            email=self.cleaned_data["email"],
            password=generated_password,
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
        )

        recipient = super().save(commit=False)
        recipient.user = user
        if hasattr(self.request.user, "socialworker"):
            recipient.social_center = self.request.user.socialworker.social_center

        if commit:
            recipient.save()

        send_account_welcome_email(
            user,
            login_url=settings.MOBILE_APP_CALLBACK_URL,
            request=self.request,
        )
        return recipient


class RecipientStaffCreationForm(forms.ModelForm):
    """
    Custom form for creating a Recipient, used by staff.
    Exposes social_center as a selectable field.
    """

    email = forms.EmailField(required=True, help_text="Email address for the new user")
    first_name = forms.CharField(required=True, max_length=150)
    last_name = forms.CharField(required=True, max_length=150)

    class Meta:
        model = Recipient
        fields = [
            "email",
            "first_name",
            "last_name",
            "social_center",
        ]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        """Create the linked CustomUser then the Recipient."""
        generated_password = secrets.token_urlsafe(20)
        user = CustomUser.objects.create_user(
            email=self.cleaned_data["email"],
            password=generated_password,
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
        )

        recipient = super().save(commit=False)
        recipient.user = user

        if commit:
            recipient.save()

        send_account_welcome_email(
            user,
            login_url=settings.MOBILE_APP_CALLBACK_URL,
            request=self.request,
        )
        return recipient


# ---------------------------------------------------------------------------
# Admin classes
# ---------------------------------------------------------------------------


class SocialCenterAdmin(AddressLocationAdminMixin, admin.ModelAdmin):
    """
    Custom admin for SocialCenter model with address autocomplete
    and interactive map display.
    """

    form = SocialCenterAdminForm
    list_display = [
        "name",
        "mail",
        "full_address",
        "city",
        "postal_code",
        "has_coordinates",
    ]
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


class SocialWorkerMainAdmin(admin.ModelAdmin):
    """Standard admin for SocialWorker model (main admin site / superusers)."""

    list_display = [
        "get_email",
        "get_first_name",
        "get_last_name",
        "social_center",
        "is_social_admin",
    ]
    list_filter = ["is_social_admin", "social_center"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    autocomplete_fields = ["user", "social_center"]

    fieldsets = (
        ("User Information", {"fields": ("user",)}),
        ("Social Center", {"fields": ("social_center",)}),
        ("Role", {"fields": ("is_social_admin",)}),
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


class SocialWorkerAdmin(admin.ModelAdmin):
    """
    Admin for managing social workers in the social_center.
    Only accessible to social admins.
    """

    list_display = [
        "get_email",
        "get_first_name",
        "get_last_name",
        "social_center",
    ]
    list_filter = ["is_social_admin", "social_center"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    autocomplete_fields = ["user", "social_center"]

    fieldsets = (
        ("User Information", {"fields": ("user",)}),
        ("Social Center", {"fields": ("social_center",)}),
        ("Role", {"fields": ("is_social_admin",)}),
    )

    add_fieldsets = (
        (
            "User Information",
            {"fields": ("email", "first_name", "last_name")},
        ),
    )

    add_fieldsets_staff = (
        (
            "User Information",
            {"fields": ("email", "first_name", "last_name")},
        ),
        (
            "Social Center",
            {"fields": ("social_center",)},
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
        if obj is None:
            return self.add_fieldsets_staff if request.user.is_staff else self.add_fieldsets
        return super().get_fieldsets(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        """
        Use staff form (with social_center) or social admin form depending on
        user.
        """
        if obj is None:
            kwargs["form"] = SocialWorkerStaffCreationForm if request.user.is_staff else SocialWorkerCreationForm
            form_class = super().get_form(request, obj, **kwargs)

            class FormWithRequest(form_class):
                def __init__(self, *args, **form_kwargs):
                    form_kwargs["request"] = request
                    super().__init__(*args, **form_kwargs)

            return FormWithRequest
        return super().get_form(request, obj, **kwargs)

    def get_queryset(self, request):
        """Filter social workers by social center. Staff see all."""
        qs = super().get_queryset(request)
        if request.user.is_staff:
            return qs
        if hasattr(request.user, "socialworker"):
            return qs.filter(social_center=request.user.socialworker.social_center)
        return qs.none()

    def is_from_same_social_center(self, request, obj):
        return (
            hasattr(request.user, "socialworker")
            and request.user.socialworker is not None
            and request.user.socialworker.is_social_admin
            and obj.social_center == request.user.socialworker.social_center
            and obj.user != request.user
        )

    def has_view_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if obj is None:
            return (
                hasattr(request.user, "socialworker")
                and request.user.socialworker.is_social_admin
                or request.user.is_staff
            )
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
        return self.is_from_same_social_center(request, obj) or request.user.is_staff

    def has_module_permission(self, request):
        return (
            request.user.is_authenticated
            and hasattr(request.user, "socialworker")
            and request.user.socialworker.is_social_admin
            or request.user.is_staff
        )


class RecipientAdmin(admin.ModelAdmin):
    """
    Standard admin for Recipient model (main admin site / superusers).
    No role-specific restrictions — relies on Django's default permissions.
    """

    list_display = [
        "get_email",
        "get_first_name",
        "get_last_name",
        "social_center",
    ]
    list_filter = ["social_center"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    autocomplete_fields = ["user", "social_center"]

    fieldsets = (("User Information", {"fields": ("user", "social_center")}),)

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


class SocialRecipientAdmin(admin.ModelAdmin):
    """
    Restricted admin for Recipient model, used in the social admin site.
    Limits visibility to recipients from the user's own social center.
    """

    list_display = [
        "get_email",
        "get_first_name",
        "get_last_name",
        "social_center",
    ]
    list_filter = ["social_center"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    autocomplete_fields = ["user", "social_center"]

    fieldsets = (
        ("User Information", {"fields": ("user",)}),
        ("Social Center", {"fields": ("social_center",)}),
    )

    add_fieldsets = (
        (
            "User Information",
            {"fields": ("email", "first_name", "last_name")},
        ),
    )

    add_fieldsets_staff = (
        (
            "User Information",
            {"fields": ("email", "first_name", "last_name")},
        ),
        (
            "Social Center",
            {"fields": ("social_center",)},
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
        if obj is None:
            return self.add_fieldsets_staff if request.user.is_staff else self.add_fieldsets
        return super().get_fieldsets(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        """
        Use staff form (with social_center) or social admin form depending on
        user.
        """
        if obj is None:
            kwargs["form"] = RecipientStaffCreationForm if request.user.is_staff else RecipientCreationForm
            form_class = super().get_form(request, obj, **kwargs)

            class FormWithRequest(form_class):
                def __init__(self, *args, **form_kwargs):
                    form_kwargs["request"] = request
                    super().__init__(*args, **form_kwargs)

            return FormWithRequest
        return super().get_form(request, obj, **kwargs)

    def get_queryset(self, request):
        """
        Return only recipients from the user's social center.
        Staff users see all recipients.
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
            and obj.user != request.user
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


class HiddenSocialCenterAdmin(admin.ModelAdmin):
    """
    Minimal SocialCenter admin registered on sub-sites solely to enable
    autocomplete_fields on models that reference SocialCenter.
    Hidden from the navigation (has_module_permission returns False).
    """

    search_fields = ["name"]

    def has_view_permission(self, request, obj=None):
        return request.user.is_authenticated and (request.user.is_staff or hasattr(request.user, "socialworker"))

    def has_module_permission(self, request):
        return False


# ---------------------------------------------------------------------------
# Social admin site
# ---------------------------------------------------------------------------


class SocialAdminSite(CustomAdminSite):
    """
    Custom admin site for social workers and social admins.
    Accessible at /social-admin/
    """

    site_header = "Social Center Admin"
    site_title = "Social Center"
    index_title = "Welcome to social center interface"

    def check_user_permission(self, user):
        """Check if user has a social admin role."""
        return user.role == UserRole.SOCIAL_ADMIN.value or user.is_staff

    def get_permission_denied_message(self):
        """Custom message for social admin access denied."""
        return "You do not have permission to access the social center admin page."


# ---------------------------------------------------------------------------
# Register models on main admin site
# ---------------------------------------------------------------------------

admin.site.register(SocialCenter, SocialCenterAdmin)
admin.site.register(SocialWorker, SocialWorkerMainAdmin)
admin.site.register(Recipient, RecipientAdmin)

# ---------------------------------------------------------------------------
# Social admin site instance
# ---------------------------------------------------------------------------

social_admin_site = SocialAdminSite(name="social_admin")
social_admin_site.register(CustomUser, HiddenCustomUserAdmin)
social_admin_site.register(SocialCenter, HiddenSocialCenterAdmin)
social_admin_site.register(Shop, SocialShopAdmin)
social_admin_site.register(SocialWorker, SocialWorkerAdmin)
social_admin_site.register(Recipient, SocialRecipientAdmin)

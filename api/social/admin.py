import secrets

from django import forms
from django.conf import settings
from django.contrib import admin
from django.db import transaction

from api.admin_sites import (
    AddressLocationAdminForm,
    AddressLocationAdminMixin,
    CustomAdminSite,
)
from api.emails import send_account_welcome_email
from api.enums import UserRole
from api.models import Cashier, CustomUser, Recipient, Shop, SocialCenter, SocialWorker
from api.shops.admin import SocialShopAdmin
from api.users.admin import HiddenCustomUserAdmin

# ---------------------------------------------------------------------------
# Admin forms
# ---------------------------------------------------------------------------


class UserInfoChangeForm(forms.ModelForm):
    """
    Base form for editing models with a linked CustomUser.

    Exposes first_name, last_name and email as directly editable fields
    without rendering a User FK selector. The read-only user metadata
    (last_login, is_active, date_joined) is displayed via admin methods.
    """

    first_name = forms.CharField(required=True, max_length=150, label="First name")
    last_name = forms.CharField(required=True, max_length=150, label="Last name")
    email = forms.EmailField(required=True, label="Email")

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance")
        if instance and instance.pk and hasattr(instance, "user"):
            initial = kwargs.setdefault("initial", {})
            initial.setdefault("first_name", instance.user.first_name)
            initial.setdefault("last_name", instance.user.last_name)
            initial.setdefault("email", instance.user.email)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        """Save editable user fields back to the linked CustomUser."""
        instance = super().save(commit=False)
        user = instance.user
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            instance.save()
            self.save_m2m()
        return instance


class SocialWorkerChangeForm(UserInfoChangeForm):
    """Change form for SocialWorker: exposes user fields inline."""

    class Meta:
        model = SocialWorker
        fields = ["social_center", "is_social_admin"]


class SocialRecipientChangeForm(UserInfoChangeForm):
    """Change form for Recipient: exposes user fields inline."""

    class Meta:
        model = Recipient
        fields = ["social_center"]


class SocialCashierCreationForm(forms.ModelForm):
    """
    Form for creating a shop manager (cashier with is_shop_manager=True)
    from the social admin site. Shop choices are restricted to shops linked
    to the social worker's own social center.
    """

    email = forms.EmailField(required=True, label="Email")
    first_name = forms.CharField(required=True, max_length=150, label="First name")
    last_name = forms.CharField(required=True, max_length=150, label="Last name")

    class Meta:
        model = Cashier
        fields = ["email", "first_name", "last_name", "shop"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        if self.request and hasattr(self.request.user, "socialworker"):
            social_center = self.request.user.socialworker.social_center
            self.fields["shop"].queryset = Shop.objects.filter(social_center=social_center)

    def save(self, commit=True):
        """Create the linked CustomUser then the Cashier with shop manager role."""
        if not self.request or not hasattr(self.request.user, "socialworker"):
            raise forms.ValidationError("Cannot create cashier, insufficient rights.")

        generated_password = secrets.token_urlsafe(20)
        with transaction.atomic():
            user = CustomUser.objects.create_user(
                email=self.cleaned_data["email"],
                password=generated_password,
                first_name=self.cleaned_data["first_name"],
                last_name=self.cleaned_data["last_name"],
            )

            cashier = super().save(commit=False)
            cashier.user = user
            cashier.is_shop_manager = True

            if commit:
                cashier.save()

            request = self.request
            transaction.on_commit(
                lambda: send_account_welcome_email(
                    user,
                    callback_url="/shop-admin/login/",
                    request=request,
                )
            )
        return cashier


class SocialCashierChangeForm(UserInfoChangeForm):
    """Change form for Cashier: exposes user fields inline."""

    class Meta:
        model = Cashier
        fields = []


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
        with transaction.atomic():
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

            request = self.request
            transaction.on_commit(
                lambda: send_account_welcome_email(
                    user,
                    callback_url="/social-admin/login/",
                    request=request,
                )
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
        with transaction.atomic():
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

            request = self.request
            transaction.on_commit(
                lambda: send_account_welcome_email(
                    user,
                    callback_url="/social-admin/login/",
                    request=request,
                )
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
        with transaction.atomic():
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

            request = self.request
            transaction.on_commit(
                lambda: send_account_welcome_email(
                    user,
                    callback_url=settings.MOBILE_APP_CALLBACK_URL,
                    request=request,
                )
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
        with transaction.atomic():
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

            request = self.request
            transaction.on_commit(
                lambda: send_account_welcome_email(
                    user,
                    callback_url=settings.MOBILE_APP_CALLBACK_URL,
                    request=request,
                )
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
    autocomplete_fields = ["social_center"]

    edit_fieldsets = (
        (
            "User Information",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "get_user_last_login",
                    "get_user_is_active",
                    "get_user_date_joined",
                )
            },
        ),
        ("Social Center", {"fields": ("get_sc_name", "get_sc_mail", "get_sc_address")}),
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

    def get_user_last_login(self, obj):
        """Display the last login date of the linked user."""
        return obj.user.last_login or "Never"

    get_user_last_login.short_description = "Last login"

    def get_user_is_active(self, obj):
        """Display the active status of the linked user."""
        return obj.user.is_active

    get_user_is_active.short_description = "Active"
    get_user_is_active.boolean = True

    def get_user_date_joined(self, obj):
        """Display the date the linked user joined."""
        return obj.user.date_joined

    get_user_date_joined.short_description = "Date joined"

    def get_sc_name(self, obj):
        """Display the social center name."""
        return obj.social_center.name

    get_sc_name.short_description = "Name"

    def get_sc_mail(self, obj):
        """Display the social center email."""
        return obj.social_center.mail

    get_sc_mail.short_description = "Email"

    def get_sc_address(self, obj):
        """Display the social center address."""
        sc = obj.social_center
        parts = filter(
            None,
            [
                f"{sc.street_number} {sc.street_name}".strip(),
                f"{sc.postal_code} {sc.city}".strip(),
            ],
        )
        return ", ".join(parts) or "—"

    get_sc_address.short_description = "Address"

    def get_readonly_fields(self, request, obj=None):
        """User metadata and social center are read-only when editing."""
        if obj is not None:
            return [
                "get_user_last_login",
                "get_user_is_active",
                "get_user_date_joined",
                "get_sc_name",
                "get_sc_mail",
                "get_sc_address",
            ]
        return []

    def get_fieldsets(self, request, obj=None):
        """Use edit fieldsets when editing, add fieldsets when creating."""
        if obj is None:
            return self.add_fieldsets_staff if request.user.is_staff else self.add_fieldsets
        return self.edit_fieldsets

    def get_autocomplete_fields(self, request):
        """Only use autocomplete for social_center when creating."""
        return ["social_center"]

    def get_form(self, request, obj=None, **kwargs):
        """
        Use the creation form for new objects and the change form (with
        inline user fields) for existing ones.
        """
        if obj is None:
            kwargs["form"] = SocialWorkerStaffCreationForm if request.user.is_staff else SocialWorkerCreationForm
            form_class = super().get_form(request, obj, **kwargs)

            class FormWithRequest(form_class):
                def __init__(self, *args, **form_kwargs):
                    form_kwargs["request"] = request
                    super().__init__(*args, **form_kwargs)

            return FormWithRequest
        kwargs["form"] = SocialWorkerChangeForm
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
    autocomplete_fields = ["social_center"]

    edit_fieldsets = (
        (
            "User Information",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "get_user_last_login",
                    "get_user_is_active",
                    "get_user_date_joined",
                )
            },
        ),
        ("Social Center", {"fields": ("get_sc_name", "get_sc_mail", "get_sc_address")}),
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

    def get_user_last_login(self, obj):
        """Display the last login date of the linked user."""
        return obj.user.last_login or "Never"

    get_user_last_login.short_description = "Last login"

    def get_user_is_active(self, obj):
        """Display the active status of the linked user."""
        return obj.user.is_active

    get_user_is_active.short_description = "Active"
    get_user_is_active.boolean = True

    def get_user_date_joined(self, obj):
        """Display the date the linked user joined."""
        return obj.user.date_joined

    get_user_date_joined.short_description = "Date joined"

    def get_sc_name(self, obj):
        """Display the social center name."""
        return obj.social_center.name

    get_sc_name.short_description = "Name"

    def get_sc_mail(self, obj):
        """Display the social center email."""
        return obj.social_center.mail

    get_sc_mail.short_description = "Email"

    def get_sc_address(self, obj):
        """Display the social center address."""
        sc = obj.social_center
        parts = filter(
            None,
            [
                f"{sc.street_number} {sc.street_name}".strip(),
                f"{sc.postal_code} {sc.city}".strip(),
            ],
        )
        return ", ".join(parts) or "—"

    get_sc_address.short_description = "Address"

    def get_readonly_fields(self, request, obj=None):
        """User metadata and social center are read-only when editing."""
        if obj is not None:
            return [
                "get_user_last_login",
                "get_user_is_active",
                "get_user_date_joined",
                "get_sc_name",
                "get_sc_mail",
                "get_sc_address",
            ]
        return []

    def get_fieldsets(self, request, obj=None):
        """Use edit fieldsets when editing, add fieldsets when creating."""
        if obj is None:
            return self.add_fieldsets_staff if request.user.is_staff else self.add_fieldsets
        return self.edit_fieldsets

    def get_autocomplete_fields(self, request):
        """Only use autocomplete for social_center when creating."""
        return ["social_center"]

    def get_form(self, request, obj=None, **kwargs):
        """
        Use the creation form for new objects and the change form (with
        inline user fields) for existing ones.
        """
        if obj is None:
            kwargs["form"] = RecipientStaffCreationForm if request.user.is_staff else RecipientCreationForm
            form_class = super().get_form(request, obj, **kwargs)

            class FormWithRequest(form_class):
                def __init__(self, *args, **form_kwargs):
                    form_kwargs["request"] = request
                    super().__init__(*args, **form_kwargs)

            return FormWithRequest
        kwargs["form"] = SocialRecipientChangeForm
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


class SocialCashierAdmin(admin.ModelAdmin):
    """
    Admin for managing shop managers (cashiers with is_shop_manager=True)
    in the social admin site. Social admins can create and manage shop
    managers for shops linked to their social center.
    """

    list_display = [
        "get_email",
        "get_first_name",
        "get_last_name",
        "shop",
    ]
    search_fields = ["user__email", "user__first_name", "user__last_name"]

    edit_fieldsets = (
        (
            "User Information",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "get_user_last_login",
                    "get_user_is_active",
                    "get_user_date_joined",
                )
            },
        ),
        ("Shop", {"fields": ("get_shop_name", "get_shop_address")}),
    )

    add_fieldsets = (
        (
            "User Information",
            {"fields": ("email", "first_name", "last_name")},
        ),
        (
            "Shop Assignment",
            {"fields": ("shop",)},
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

    def get_user_last_login(self, obj):
        """Display the last login date of the linked user."""
        return obj.user.last_login or "Never"

    get_user_last_login.short_description = "Last login"

    def get_user_is_active(self, obj):
        """Display the active status of the linked user."""
        return obj.user.is_active

    get_user_is_active.short_description = "Active"
    get_user_is_active.boolean = True

    def get_user_date_joined(self, obj):
        """Display the date the linked user joined."""
        return obj.user.date_joined

    get_user_date_joined.short_description = "Date joined"

    def get_shop_name(self, obj):
        """Display the cashier's shop name."""
        return obj.shop.name

    get_shop_name.short_description = "Shop name"

    def get_shop_address(self, obj):
        """Display the cashier's shop address."""
        shop = obj.shop
        parts = filter(
            None,
            [
                f"{shop.street_number} {shop.street_name}".strip(),
                f"{shop.postal_code} {shop.city}".strip(),
            ],
        )
        return ", ".join(parts) or "—"

    get_shop_address.short_description = "Address"

    def get_readonly_fields(self, request, obj=None):
        """User info and shop are read-only when editing."""
        if obj is not None:
            return [
                "get_user_last_login",
                "get_user_is_active",
                "get_user_date_joined",
                "get_shop_name",
                "get_shop_address",
            ]
        return []

    def get_fieldsets(self, request, obj=None):
        """Use edit fieldsets when editing, add fieldsets when creating."""
        if obj is None:
            return self.add_fieldsets
        return self.edit_fieldsets

    def get_form(self, request, obj=None, **kwargs):
        """
        Use creation form for new objects and the change form (with inline
        user fields) for existing ones.
        """
        if obj is None:
            kwargs["form"] = SocialCashierCreationForm
            form_class = super().get_form(request, obj, **kwargs)
            admin_site = self.admin_site

            class FormWithRequest(form_class):
                def __init__(self, *args, **form_kwargs):
                    from django.contrib.admin.widgets import AutocompleteSelect

                    from api.models import Cashier as CashierModel

                    form_kwargs["request"] = request
                    super().__init__(*args, **form_kwargs)
                    db_field = CashierModel._meta.get_field("shop")
                    widget = AutocompleteSelect(db_field, admin_site)
                    # AutocompleteSelect.optgroups expects self.choices to be
                    # a ModelChoiceIterator, not a plain list. Assign the
                    # field's iterator to the new widget before swapping.
                    widget.choices = self.fields["shop"].choices
                    self.fields["shop"].widget = widget

            return FormWithRequest
        kwargs["form"] = SocialCashierChangeForm
        return super().get_form(request, obj, **kwargs)

    def get_queryset(self, request):
        """List only shop managers from the social admin's center."""
        qs = super().get_queryset(request)
        if request.user.is_staff:
            return qs
        if hasattr(request.user, "socialworker"):
            return qs.filter(
                shop__social_center=request.user.socialworker.social_center,
                is_shop_manager=True,
            )
        return qs.none()

    def _is_from_same_social_center(self, request, obj):
        """Check that the cashier's shop belongs to the social admin's center."""
        return (
            hasattr(request.user, "socialworker")
            and request.user.socialworker.is_social_admin
            and obj.shop.social_center == request.user.socialworker.social_center
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
    Hidden from the navigation and direct list/change views are blocked for
    non-staff users.
    """

    search_fields = ["name"]

    def has_view_permission(self, request, obj=None):
        # Allow social workers so that autocomplete queries keep working.
        # Direct changelist/change access is blocked separately.
        return request.user.is_authenticated and (request.user.is_staff or hasattr(request.user, "socialworker"))

    def has_module_permission(self, request):
        return False

    def changelist_view(self, request, extra_context=None):
        """Block direct list access for non-staff users."""
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        return super().changelist_view(request, extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """Block direct change page access for non-staff users."""
        if not request.user.is_staff:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        return super().change_view(request, object_id, form_url, extra_context)


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
social_admin_site.register(Cashier, SocialCashierAdmin)

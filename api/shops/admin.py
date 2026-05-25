import csv
import secrets
from datetime import date

from django import forms
from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from api.admin_sites import (
    AddressLocationAdminForm,
    AddressLocationAdminMixin,
    CustomAdminSite,
    UniqueEmailMixin,
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
        (_("Informations générales"), {"fields": ("name", "social_center")}),
        (
            _("Adresse"),
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
                "description": _(
                    "Commencez à saisir dans le champ adresse pour voir des suggestions. "
                    "Les champs structurés ci-dessous sont remplis automatiquement mais peuvent être modifiés."
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
        (_("Informations utilisateur"), {"fields": ("user",)}),
        (_("Affectation magasin"), {"fields": ("shop",)}),
        (_("Rôle"), {"fields": ("is_shop_manager",)}),
    )

    def get_email(self, obj):
        return obj.user.email

    get_email.short_description = _("E-mail")
    get_email.admin_order_field = "user__email"

    def get_first_name(self, obj):
        return obj.user.first_name

    get_first_name.short_description = _("Prénom")
    get_first_name.admin_order_field = "user__first_name"

    def get_last_name(self, obj):
        return obj.user.last_name

    get_last_name.short_description = _("Nom")
    get_last_name.admin_order_field = "user__last_name"


# ---------------------------------------------------------------------------
# Shop admin site
# ---------------------------------------------------------------------------


class ShopAdminSite(CustomAdminSite):
    """
    Custom admin site for shop managers and cashiers.
    Accessible at /shop-admin/
    """

    site_header = _("Gestion des magasins")
    site_title = _("Admin magasin")
    index_title = _("Bienvenue dans l'interface d'administration des magasins")

    def check_user_permission(self, user):
        """Check if user has a cashier profile or is staff."""
        return hasattr(user, "cashier") or user.is_staff

    def get_permission_denied_message(self):
        """Custom message for shop admin access denied."""
        return _("Vous n'avez pas la permission d'accéder à l'interface magasin.")


class CashierCreationForm(UniqueEmailMixin, forms.ModelForm):
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


class CashierShopChangeForm(UniqueEmailMixin, forms.ModelForm):
    """
    Change form for Cashier: exposes user fields inline and allows
    role editing. Keeps the same structure as the social admin change form.
    """

    first_name = forms.CharField(required=True, max_length=150, label="First name")
    last_name = forms.CharField(required=True, max_length=150, label="Last name")
    email = forms.EmailField(required=True, label="Email")

    class Meta:
        model = Cashier
        fields = ["is_shop_manager"]

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

    edit_fieldsets = (
        (
            _("Informations utilisateur"),
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
        (_("Magasin"), {"fields": ("get_shop_name", "get_shop_address")}),
        (_("Rôle"), {"fields": ("is_shop_manager",)}),
    )

    add_fieldsets = (
        (
            _("Informations utilisateur"),
            {"fields": ("email", "first_name", "last_name")},
        ),
        (
            _("Rôle"),
            {
                "fields": ("role",),
                "description": _("Sélectionnez si cet utilisateur doit être un caissier classique ou un responsable."),
            },
        ),
    )

    def get_email(self, obj):
        return obj.user.email

    get_email.short_description = _("E-mail")
    get_email.admin_order_field = "user__email"

    def get_first_name(self, obj):
        return obj.user.first_name

    get_first_name.short_description = _("Prénom")
    get_first_name.admin_order_field = "user__first_name"

    def get_last_name(self, obj):
        return obj.user.last_name

    get_last_name.short_description = _("Nom")
    get_last_name.admin_order_field = "user__last_name"

    def get_role(self, obj):
        return _("Responsable") if obj.is_shop_manager else _("Caissier")

    get_role.short_description = _("Rôle")

    def get_user_last_login(self, obj):
        """Display the last login date of the linked user."""
        return obj.user.last_login or _("Jamais")

    get_user_last_login.short_description = _("Dernière connexion")

    def get_user_is_active(self, obj):
        """Display the active status of the linked user."""
        return obj.user.is_active

    get_user_is_active.short_description = _("Actif")
    get_user_is_active.boolean = True

    def get_user_date_joined(self, obj):
        """Display the date the linked user joined."""
        return obj.user.date_joined

    get_user_date_joined.short_description = _("Date d'inscription")

    def get_shop_name(self, obj):
        """Display the cashier's shop name."""
        return obj.shop.name

    get_shop_name.short_description = _("Nom du magasin")

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

    get_shop_address.short_description = _("Adresse")

    def get_readonly_fields(self, request, obj=None):
        """Shop info and user metadata are read-only when editing."""
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
        """Use custom form for creation, change form with inline user fields for editing."""
        if obj is None:
            kwargs["form"] = CashierCreationForm
            form_class = super().get_form(request, obj, **kwargs)

            class FormWithRequest(form_class):
                def __init__(self, *args, **form_kwargs):
                    form_kwargs["request"] = request
                    super().__init__(*args, **form_kwargs)

            return FormWithRequest
        kwargs["form"] = CashierShopChangeForm
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


# ---------------------------------------------------------------------------
# Article export form
# ---------------------------------------------------------------------------


class ArticleExportForm(forms.Form):
    """
    Form for filtering articles by date range before CSV export.
    Both fields are optional: leaving them blank exports all articles.
    """

    date_from = forms.DateField(
        required=False,
        label=_("Du"),
        widget=forms.DateInput(
            attrs={"type": "date"},
            format="%Y-%m-%d",
        ),
    )
    date_to = forms.DateField(
        required=False,
        label=_("Au"),
        widget=forms.DateInput(
            attrs={"type": "date"},
            format="%Y-%m-%d",
        ),
    )

    def clean(self):
        """Validate that date_from is not after date_to."""
        cleaned = super().clean()
        date_from = cleaned.get("date_from")
        date_to = cleaned.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise forms.ValidationError(_("La date de début doit être antérieure à la date de fin."))
        return cleaned


class ArticleShopAdmin(admin.ModelAdmin):
    """
    Read-only admin for viewing articles in the shop.
    Accessible to both cashiers and shop managers.
    """

    change_list_template = "admin/shop_article_changelist.html"

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
            _("Informations sur l'article"),
            {"fields": ["name", "barcode", "brand_label", "get_status"]},
        ),
        (
            _("Images"),
            {"fields": ["img_url", "thumb_url"]},
        ),
        (
            _("Relations"),
            {"fields": ["client", "shop", "cart"]},
        ),
        (
            _("Horodatages"),
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

    get_status.short_description = _("Statut")

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

    # -----------------------------------------------------------------------
    # CSV export
    # -----------------------------------------------------------------------

    def get_urls(self):
        """Append a custom export-csv URL to the standard admin URLs."""
        urls = super().get_urls()
        export_url = [
            path(
                "export-csv/",
                self.admin_site.admin_view(self.export_csv_view),
                name="api_article_export_csv",
            )
        ]
        return export_url + urls

    def _is_shop_manager(self, request):
        """Return True if the request user is a shop manager (or staff)."""
        return request.user.is_staff or (hasattr(request.user, "cashier") and request.user.cashier.is_shop_manager)

    def export_csv_view(self, request):
        """
        Custom admin view that renders a date-range form (GET) and returns
        a CSV file of the shop's articles (POST). Restricted to shop managers.
        """
        if not self._is_shop_manager(request):
            self.message_user(
                request,
                _("Vous n'avez pas la permission d'exporter les articles."),
                level="error",
            )
            return redirect("{}:api_article_changelist".format(self.admin_site.name))

        today = date.today()
        initial = {
            "date_from": today.replace(day=1),
            "date_to": today,
        }
        form = ArticleExportForm(
            request.POST if request.method == "POST" else None,
            initial=initial,
        )

        if request.method == "POST" and form.is_valid():
            return self._build_csv_response(
                request,
                date_from=form.cleaned_data.get("date_from"),
                date_to=form.cleaned_data.get("date_to"),
            )

        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "title": _("Exporter les articles en CSV"),
            "opts": self.model._meta,
        }
        return render(request, "admin/article_export_form.html", context)

    def _build_csv_response(self, request, date_from, date_to):
        """
        Build and return an HttpResponse containing a CSV of articles for the
        current shop, optionally filtered by created_at date range.

        Parameters
        ----------
        request:
            The current HTTP request (used to scope the queryset to the shop).
        date_from : date | None
            Inclusive lower bound on ``created_at`` (ignored when None).
        date_to : date | None
            Inclusive upper bound on ``created_at`` (ignored when None).
        """
        qs = self.get_queryset(request).select_related("client__user", "cart")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        # UTF-8 BOM so Excel opens the file correctly without encoding issues.
        filename = f"export_resos_coeur-{date.today().isoformat()}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.write("\ufeff")

        writer = csv.writer(response)
        writer.writerow(
            [
                _("ID"),
                _("Nom"),
                _("Code-barres"),
                _("Marque"),
                _("E-mail client"),
                _("ID panier"),
                _("Statut panier"),
                _("Date de création"),
                _("Dernière mise à jour"),
            ]
        )

        for article in qs.iterator():
            cart_id = article.cart_id or ""
            cart_status = article.cart.status if article.cart else ""
            writer.writerow(
                [
                    article.id,
                    article.name,
                    article.barcode,
                    article.brand_label,
                    article.client.user.email,
                    cart_id,
                    cart_status,
                    article.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    article.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                ]
            )

        return response


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

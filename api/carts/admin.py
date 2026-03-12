from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html, mark_safe

from api.admin_sites import CustomAdminSite
from api.enums import UserRole
from api.models import Article, Cart, Recipient, Shop

from .forms import ArticleToCartForm, CartChangeForm, CartCreationForm


class CartAdmin(admin.ModelAdmin):
    readonly_fields = ["status"]
    list_display = ["id", "shop", "recipient", "status", "collected_at"]
    list_filter = ["shop", "collected_at"]
    search_fields = ["id", "shop__name", "recipient__user__email"]
    autocomplete_fields = ["shop", "recipient"]


admin.site.register(Cart, CartAdmin)


# ============================================
# CART ATTRIBUTION ADMIN SITE
# ============================================


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


class HiddenShopAttrAdmin(admin.ModelAdmin):
    """Hidden admin registered solely to support autocomplete on Cart forms."""

    search_fields = ["name"]

    def get_queryset(self, request):
        """Restrict shops to the social worker's social center."""
        qs = super().get_queryset(request)
        if request.user.is_staff:
            return qs
        if hasattr(request.user, "socialworker"):
            return qs.filter(social_center=request.user.socialworker.social_center)
        return qs.none()

    def has_view_permission(self, request, obj=None):
        return request.user.is_authenticated and (request.user.is_staff or hasattr(request.user, "socialworker"))

    def has_module_permission(self, request):
        return False


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

    def get_queryset(self, request):
        """Restrict recipients to the social worker's social center."""
        qs = super().get_queryset(request)
        if request.user.is_staff:
            return qs
        if hasattr(request.user, "socialworker"):
            return qs.filter(social_center=request.user.socialworker.social_center)
        return qs.none()

    def is_from_same_social_center(self, request, obj):
        return hasattr(request.user, "socialworker") and obj.social_center == request.user.socialworker.social_center

    def has_view_permission(self, request, obj=None):
        if not request.user.is_authenticated:
            return False
        if obj is None:
            return hasattr(request.user, "socialworker") or request.user.is_staff
        return self.is_from_same_social_center(request, obj) or request.user.is_staff

    def has_module_permission(self, request):
        return request.user.is_staff or (request.user.is_authenticated and hasattr(request.user, "socialworker"))


from django_admin_action_forms import AdminActionFormsMixin, action_with_form  # noqa: E402


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

    @action_with_form(ArticleToCartForm, description="Assign Article to Cart")
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
            return mark_safe('<span style="color: orange; font-weight: bold;">' "Panier assigné</span>")
        else:
            return mark_safe('<span style="color: blue; font-weight: bold;">' "Panier non assigné</span>")

    get_status.short_description = "Statut"

    def get_cart_link(self, obj):
        """Clickable link to the cart change page, or a dash if not in any
        cart."""
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
        if not request.user.is_authenticated:
            return False
        return hasattr(request.user, "socialworker") or request.user.is_staff

    def has_module_permission(self, request):
        return request.user.is_authenticated and (hasattr(request.user, "socialworker") or request.user.is_staff)


class CartAttribAdmin(admin.ModelAdmin):
    list_display = ["id", "shop", "status", "collected_at"]
    autocomplete_fields = ["shop", "recipient"]

    def get_articles_display(self, obj: "Cart") -> str:
        """
        Render the list of articles in a collected cart as a
        comma-separated read-only string.
        """
        articles = obj.articles.order_by("name")
        if not articles.exists():
            return "—"
        items = [f"{a.name} ({a.brand_label})" if a.brand_label else a.name for a in articles]
        return ", ".join(items)

    get_articles_display.short_description = "Articles dans le panier"

    def get_fields(self, request, obj=None):
        """
        Different fields for creation vs editing.

        For a COLLECTED cart, replace the editable ``articles`` widget
        with the read-only ``get_articles_display`` method so that
        Django admin can render every field as plain text.
        """
        if obj is None:
            return ["shop", "recipient"]
        if obj.status == "COLLECTED":
            return ["shop", "recipient", "collected_at", "get_articles_display"]
        return ["shop", "recipient", "collected_at", "articles"]

    def get_readonly_fields(self, request, obj=None):
        """
        Shop and collected_at are readonly when editing.

        For COLLECTED carts all fields are readonly so that the
        change view opens in pure view-only mode without any editable
        widget.
        """
        if obj is None:
            return []
        if obj.status == "COLLECTED":
            return ["shop", "recipient", "collected_at", "get_articles_display"]
        return ["shop", "collected_at"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Restrict shop/recipient choices to the social worker's social center.

        Staff users see all records; social workers see only records linked to
        their own social center.
        """
        if not request.user.is_staff and hasattr(request.user, "socialworker"):
            sc = request.user.socialworker.social_center
            if db_field.name == "shop":
                kwargs["queryset"] = Shop.objects.filter(social_center=sc)
            elif db_field.name == "recipient":
                kwargs["queryset"] = Recipient.objects.filter(social_center=sc)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        """Use CartCreationForm for new carts, CartChangeForm for editing."""
        kwargs["form"] = CartCreationForm if obj is None else CartChangeForm
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
        """Check if user has a social worker, social admin role, or is staff."""
        return user.is_staff or user.role == UserRole.SOCIAL_ADMIN.value or user.role == UserRole.SOCIAL_WORKER.value

    def get_permission_denied_message(self):
        """Custom message for cart attribution access denied."""
        return "You do not have permission to access the social center admin page."


cart_attrib_admin_site = CartAttributionAdminSite(name="cart_attrib_admin")
cart_attrib_admin_site.register(Shop, HiddenShopAttrAdmin)
cart_attrib_admin_site.register(Recipient, RecipientAttrAdmin)
cart_attrib_admin_site.register(Article, ArticleAttrAdmin)
cart_attrib_admin_site.register(Cart, CartAttribAdmin)

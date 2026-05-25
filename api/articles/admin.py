from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from api.models import Article


class ArticleAdmin(ModelAdmin):
    list_display = [
        "id",
        "name",
        "barcode",
        "brand_label",
        "client",
        "shop",
        "cart",
        "created_at",
    ]
    list_filter = ["shop", "created_at", "cart"]
    search_fields = ["barcode", "brand_label", "name", "client__user__email"]
    readonly_fields = ["created_at", "updated_at"]
    autocomplete_fields = ["client", "shop", "cart"]
    fieldsets = [
        (
            _("Informations sur l'article"),
            {
                "fields": ["name", "barcode", "brand_label"],
            },
        ),
        (
            _("Images"),
            {
                "fields": ["img_url", "thumb_url"],
            },
        ),
        (
            _("Relations"),
            {
                "fields": ["client", "shop", "cart"],
            },
        ),
        (
            _("Horodatages"),
            {
                "fields": ["created_at", "updated_at"],
            },
        ),
    ]


admin.site.register(Article, ArticleAdmin)

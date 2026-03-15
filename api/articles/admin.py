from django.contrib import admin

from api.models import Article


class ArticleAdmin(admin.ModelAdmin):
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

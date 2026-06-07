from django.db import models
from django.utils.translation import gettext_lazy as _

from .carts import Cart
from .shops import Shop
from .users import Client


class Article(models.Model):
    name = models.CharField(max_length=500, blank=True, default="")
    barcode = models.BigIntegerField()
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="articles")
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="articles")
    cart = models.ForeignKey(Cart, null=True, blank=True, on_delete=models.CASCADE, related_name="articles")
    img_url = models.URLField(max_length=500, blank=True, default="")
    thumb_url = models.URLField(max_length=500, blank=True, default="")
    brand_label = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("article")
        verbose_name_plural = _("articles")
        indexes = [
            models.Index(fields=["barcode"]),
            # Composite index optimizing the most frequent query pattern:
            # articles available in a given shop (cart__isnull=True filters
            # are applied on top of a shop filter by social workers).
            models.Index(fields=["shop", "cart"], name="article_shop_cart_idx"),
        ]

    @staticmethod
    def truncate_name(value: str) -> str:
        """Truncate a name value to the field's max_length (500)."""
        max_length = 500  # mirrors Article.name max_length
        return value[:max_length] if value else value

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        """Persist the article after trimming the name to the DB limit."""
        self.name = self.truncate_name(self.name)
        super().save(*args, **kwargs)

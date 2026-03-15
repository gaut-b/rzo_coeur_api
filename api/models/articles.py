from django.db import models

from .carts import Cart
from .shops import Shop
from .users import Client


class Article(models.Model):
    name = models.CharField(max_length=50, blank=True, default="")
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
        indexes = [models.Index(fields=["barcode"])]

    def __str__(self) -> str:
        return self.name

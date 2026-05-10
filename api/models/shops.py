from django.db import models
from django.utils.translation import gettext_lazy as _

from .base import AddressLocationMixin
from .social import SocialCenter
from .users import CustomUser


class Shop(AddressLocationMixin):
    name = models.CharField(max_length=100)
    social_center = models.ForeignKey(SocialCenter, on_delete=models.CASCADE, related_name="shops")

    class Meta:
        verbose_name = _("magasin")
        verbose_name_plural = _("magasins")

    def __str__(self) -> str:
        return self.name


class Cashier(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="cashiers")
    is_shop_manager = models.BooleanField(
        default=False,
        help_text="Designates whether this cashier can manage other cashiers",
    )

    def __str__(self) -> str:
        role = "Manager" if self.is_shop_manager else "Cashier"
        return f"{self.user} ({role} at {self.shop.name})"

    class Meta:
        verbose_name = _("vendeur")
        verbose_name_plural = _("vendeurs")

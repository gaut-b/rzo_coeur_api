from typing import TYPE_CHECKING

from django.db import models
from django.utils.translation import gettext_lazy as _

from .base import AddressLocationMixin
from .users import CustomUser

if TYPE_CHECKING:
    from django.db.models import Manager

    RelatedManager = Manager

    from .carts import Cart
    from .shops import Shop


class SocialCenter(AddressLocationMixin):
    name = models.CharField(max_length=50)
    mail = models.CharField(max_length=200)

    class Meta:
        verbose_name = _("centre social")
        verbose_name_plural = _("centres sociaux")

    if TYPE_CHECKING:
        social_workers: "RelatedManager[SocialWorker]"
        recipients: "RelatedManager[Recipient]"
        shops: "RelatedManager[Shop]"

    def __str__(self) -> str:
        return self.name


class SocialWorker(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    social_center = models.ForeignKey(SocialCenter, on_delete=models.CASCADE, related_name="social_workers")
    is_social_admin = models.BooleanField(
        default=False,
        help_text="Designates whether this social worker can create users and shops.",
    )

    class Meta:
        verbose_name = _("travailleur social")
        verbose_name_plural = _("travailleurs sociaux")

    def __str__(self) -> str:
        return str(self.user)


class Recipient(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    social_center = models.ForeignKey(SocialCenter, on_delete=models.CASCADE, related_name="recipients")

    class Meta:
        verbose_name = _("bénéficiaire")
        verbose_name_plural = _("bénéficiaires")

    if TYPE_CHECKING:
        carts: "RelatedManager[Cart]"

    def __str__(self) -> str:
        return str(self.user)

from typing import TYPE_CHECKING

from django.db import models
from django.utils.translation import gettext_lazy as _

from ..enums import CartStatus
from .shops import Shop
from .social import Recipient

if TYPE_CHECKING:
    from django.db.models import Manager

    RelatedManager = Manager

    from .articles import Article


class CartQuerySet(models.QuerySet):
    """Custom QuerySet for Cart with status-based filtering methods."""

    def by_status(self, status: str) -> "CartQuerySet":
        """
        Filter carts by their computed status.

        Maps the logical status to the underlying field conditions used
        by the Cart.status property, so filtering stays consistent with
        the model definition.

        Parameters:
            status (str): One of 'PENDING', 'ASSIGNED', or 'COLLECTED'.

        Returns:
            CartQuerySet: Filtered queryset matching the given status.
        """
        if status == CartStatus.PENDING.value:
            return self.filter(recipient__isnull=True)
        if status == CartStatus.ASSIGNED.value:
            return self.filter(recipient__isnull=False, collected_at__isnull=True)
        if status == CartStatus.COLLECTED.value:
            return self.filter(collected_at__isnull=False)
        raise ValueError(f"Invalid cart status: '{status}'.")


class Cart(models.Model):
    id: int  # type: ignore[assignment]
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="carts")
    recipient = models.ForeignKey(Recipient, on_delete=models.CASCADE, related_name="carts", null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    objects: CartQuerySet = CartQuerySet.as_manager()  # type: ignore[assignment]

    if TYPE_CHECKING:
        articles: "RelatedManager[Article]"

    class Meta:
        verbose_name = _("panier")
        verbose_name_plural = _("paniers")

    @property
    def status(self) -> str:
        """
        Computed status based on recipient and collected_at fields.
        - COLLECTED: if collected_at is set
        - ASSIGNED: if recipient is set but not yet collected
        - PENDING: if no recipient assigned
        """
        if self.collected_at is not None and self.recipient is not None:
            return CartStatus.COLLECTED.value
        if self.recipient is not None and self.collected_at is None:
            return CartStatus.ASSIGNED.value
        return CartStatus.PENDING.value

    def __str__(self) -> str:
        date_str = self.created_at.strftime("%d/%m/%Y") if self.created_at else "—"
        return f"#{self.id} — {self.shop.name} — {date_str}"

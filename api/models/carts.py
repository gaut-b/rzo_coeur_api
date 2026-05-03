from typing import TYPE_CHECKING

from django.db import models

from ..enums import CartStatus
from .shops import Shop
from .social import Recipient

if TYPE_CHECKING:
    from django.db.models import Manager

    RelatedManager = Manager

    from .articles import Article


class Cart(models.Model):
    id: int  # type: ignore[assignment]
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="carts")
    recipient = models.ForeignKey(Recipient, on_delete=models.CASCADE, related_name="carts", null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    if TYPE_CHECKING:
        articles: "RelatedManager[Article]"

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

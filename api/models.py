from typing import TYPE_CHECKING

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from .enums import CartStatus, UserRole
from .managers import CustomUserManager

if TYPE_CHECKING:
    from django.db.models import Manager

    RelatedManager = Manager


class CustomUser(AbstractUser):
    username = None  # type: ignore
    email = models.EmailField(_("email address"), unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = CustomUserManager()  # type: ignore[assignment]

    if TYPE_CHECKING:
        client: "Client"
        socialworker: "SocialWorker"
        recipient: "Recipient"
        cashier: "Cashier"

    def __str__(self) -> str:
        full_name = self.get_full_name()
        return full_name if full_name else self.email

    @property
    def role(self) -> str | None:
        """
        Determines the user's role based on their relationships.
        Returns the role or None if no role is found.
        Caches the result to avoid repeated database queries.
        """
        if not hasattr(self, "_cached_role"):
            if hasattr(self, "client"):
                self._cached_role = UserRole.CLIENT.value
            elif hasattr(self, "socialworker"):
                self._cached_role = UserRole.SOCIAL_WORKER.value
            elif hasattr(self, "recipient"):
                self._cached_role = UserRole.RECIPIENT.value
            elif hasattr(self, "cashier"):
                self._cached_role = UserRole.CASHIER.value
            else:
                self._cached_role = None
        return self._cached_role


class Client(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)

    if TYPE_CHECKING:
        articles: "RelatedManager[Article]"

    def __str__(self) -> str:
        return str(self.user)


class SocialCenter(models.Model):
    name = models.CharField(max_length=50)
    address = models.CharField(max_length=200)
    mail = models.CharField(max_length=200)

    if TYPE_CHECKING:
        social_workers: "RelatedManager[SocialWorker]"
        recipients: "RelatedManager[Recipient]"
        shops: "RelatedManager[Shop]"

    def __str__(self) -> str:
        return self.name


class SocialWorker(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    social_center = models.ForeignKey(
        SocialCenter, on_delete=models.CASCADE, related_name="social_workers"
    )

    def __str__(self) -> str:
        return str(self.user)


class Recipient(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    social_center = models.ForeignKey(
        SocialCenter, on_delete=models.CASCADE, related_name="recipients"
    )

    if TYPE_CHECKING:
        carts: "RelatedManager[Cart]"

    def __str__(self) -> str:
        return str(self.user)


class Shop(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    social_center = models.ForeignKey(SocialCenter, on_delete=models.CASCADE, related_name="shops")

    if TYPE_CHECKING:
        cashier: "Cashier"
        carts: "RelatedManager[Cart]"
        articles: "RelatedManager[Article]"

    def __str__(self) -> str:
        return self.name


class Cashier(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    shop = models.OneToOneField(Shop, on_delete=models.CASCADE, related_name="cashier")

    def __str__(self) -> str:
        return str(self.user)


class Cart(models.Model):
    id: int  # type: ignore[assignment]
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="carts")
    recipient = models.ForeignKey(Recipient, on_delete=models.CASCADE, related_name="carts")
    status = models.CharField(
        max_length=20,
        choices=[
            (CartStatus.PENDING.value, "Pending assignment"),
            (CartStatus.ASSIGNED.value, "Assigned to beneficiary"),
            (CartStatus.COLLECTED.value, "Collected"),
        ],
        default=CartStatus.PENDING.value,
    )
    collected_at = models.DateTimeField(null=True, blank=True)

    if TYPE_CHECKING:
        articles: "RelatedManager[Article]"

    def __str__(self) -> str:
        return f"Cart {self.id} - {self.status} - {self.shop.name}"


class Article(models.Model):
    name = models.CharField(max_length=50)
    barcode = models.BigIntegerField()
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="articles")
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="articles")
    cart = models.ForeignKey(
        Cart, null=True, blank=True, on_delete=models.CASCADE, related_name="articles"
    )

    class Meta:
        indexes = [models.Index(fields=["barcode"])]

    def __str__(self) -> str:
        return self.name

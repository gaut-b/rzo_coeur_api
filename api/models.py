from typing import TYPE_CHECKING

from django.contrib.auth.models import AbstractUser
from django.contrib.gis.db import models as gis_models
from django.db import models
from django.utils.translation import gettext_lazy as _

from .enums import CartStatus, UserRole
from .managers import CustomUserManager

if TYPE_CHECKING:
    from django.db.models import Manager

    RelatedManager = Manager


class AddressLocationMixin(models.Model):
    """
    Mixin for models with structured address fields and geographic location.
    Provides common fields and properties for address handling.
    """

    # Structured address fields (filled by geocoding from user input)
    postal_code = models.CharField(max_length=10, blank=True, help_text="Postal code")
    street_number = models.CharField(max_length=20, blank=True, help_text="Street number")
    street_name = models.CharField(max_length=200, blank=True, help_text="Street name")
    city = models.CharField(max_length=100, blank=True, help_text="City")

    # Geographic location (PostGIS)
    location = gis_models.PointField(
        geography=True,
        null=True,
        blank=True,
        help_text="Geographic coordinates (longitude, latitude)",
        srid=4326,  # WGS84 coordinate system
    )

    class Meta:
        abstract = True

    @property
    def latitude(self):
        """Get latitude from location point."""
        return self.location.y if self.location else None

    @property
    def longitude(self):
        """Get longitude from location point."""
        return self.location.x if self.location else None


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


class SocialCenter(AddressLocationMixin):
    name = models.CharField(max_length=50)
    mail = models.CharField(max_length=200)

    if TYPE_CHECKING:
        social_workers: "RelatedManager[SocialWorker]"
        recipients: "RelatedManager[Recipient]"
        shops: "RelatedManager[Shop]"

    def __str__(self) -> str:
        return self.name


class SocialWorker(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    social_center = models.ForeignKey(SocialCenter, on_delete=models.CASCADE, related_name="social_workers")

    def __str__(self) -> str:
        return str(self.user)


class Recipient(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    social_center = models.ForeignKey(SocialCenter, on_delete=models.CASCADE, related_name="recipients")

    if TYPE_CHECKING:
        carts: "RelatedManager[Cart]"

    def __str__(self) -> str:
        return str(self.user)


class Shop(AddressLocationMixin):
    name = models.CharField(max_length=100)
    social_center = models.ForeignKey(SocialCenter, on_delete=models.CASCADE, related_name="shops")

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
    recipient = models.ForeignKey(Recipient, on_delete=models.CASCADE, related_name="carts", null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)

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
        return f"Cart {self.id} - {self.status} - {self.shop.name}"


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

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from .enums import UserRole
from .managers import CustomUserManager


class CustomUser(AbstractUser):
    username = None
    email = models.EmailField(_("email address"), unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        full_name = self.get_full_name()
        return full_name if full_name else self.email

    @property
    def role(self):
        """
        Determines the user's role based on their relationships.
        Returns the role or None if no role is found.
        Caches the result to avoid repeated database queries.
        """
        if not hasattr(self, "_cached_role"):
            if hasattr(self, "client"):
                self._cached_role = UserRole.CLIENT
            elif hasattr(self, "socialworker"):
                self._cached_role = UserRole.SOCIAL_WORKER
            elif hasattr(self, "recipient"):
                self._cached_role = UserRole.RECIPIENT
            elif hasattr(self, "cashier"):
                self._cached_role = UserRole.CASHIER
            else:
                self._cached_role = None
        return self._cached_role


class Client(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)

    def __str__(self):
        return str(self.user)


class SocialCenter(models.Model):
    name = models.CharField(max_length=50)
    address = models.CharField(max_length=200)
    mail = models.CharField(max_length=200)

    # def switch from scanned to assigned
    # register list article to magasin
    # create_panier : get from article_scanned list to article_assigned, create a panier
    #

    def __str__(self):
        return self.name


class SocialWorker(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    social_center = models.ForeignKey(
        SocialCenter, on_delete=models.CASCADE, related_name="social_workers"
    )

    def __str__(self):
        return str(self.user)


class Recipient(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    social_center = models.ForeignKey(
        SocialCenter, on_delete=models.CASCADE, related_name="recipients"
    )
    # Methods proposal
    # - register panier

    def __str__(self):
        return str(self.user)


class Shop(models.Model):
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    social_center = models.ForeignKey(SocialCenter, on_delete=models.CASCADE, related_name="shops")
    # Methods proposal
    # - create article list
    # - notify list suspendus

    def __str__(self):
        return self.name


class Cashier(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    shop = models.OneToOneField(Shop, on_delete=models.CASCADE, related_name="cashier")

    def __str__(self):
        return str(self.user)


class Cart(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="carts")
    recipient = models.ForeignKey(Recipient, on_delete=models.CASCADE, related_name="carts")
    status = models.CharField(
        max_length=20,
        choices=[
            ("PENDING", "Pending assignment"),
            ("ASSIGNED", "Assigned to beneficiary"),
            ("COLLECTED", "Collected"),
        ],
        default="PENDING",
    )


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

    def __str__(self):
        return self.name

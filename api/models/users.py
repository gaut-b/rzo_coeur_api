from typing import TYPE_CHECKING

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from ..enums import UserRole
from ..managers import CustomUserManager

if TYPE_CHECKING:
    from django.db.models import Manager

    RelatedManager = Manager

    from .articles import Article
    from .shops import Cashier
    from .social import Recipient, SocialWorker


class CustomUser(AbstractUser):
    username = None  # type: ignore
    email = models.EmailField(_("email address"), unique=True)
    is_staff = models.BooleanField(
        _("staff"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )

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
                # Check if social worker is a social admin
                if self.socialworker.is_social_admin:
                    self._cached_role = UserRole.SOCIAL_ADMIN.value
                else:
                    self._cached_role = UserRole.SOCIAL_WORKER.value

            elif hasattr(self, "recipient"):
                self._cached_role = UserRole.RECIPIENT.value
            elif hasattr(self, "cashier"):
                # Check if cashier is a shop manager
                if self.cashier.is_shop_manager:
                    self._cached_role = UserRole.SHOP_MANAGER.value
                else:
                    self._cached_role = UserRole.CASHIER.value
            else:
                self._cached_role = None
        return self._cached_role


class Client(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)

    class Meta:
        verbose_name = _("client")
        verbose_name_plural = _("clients")

    if TYPE_CHECKING:
        articles: "RelatedManager[Article]"

    def __str__(self) -> str:
        return str(self.user)

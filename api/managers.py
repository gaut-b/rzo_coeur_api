from typing import TYPE_CHECKING, Any

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.decorators import permission_required
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from api.models import CustomUser


class CustomUserManager(BaseUserManager["CustomUser"]):
    """
    Custom user model manager where email is the unique identifier
    for authentication instead of usernames.
    """

    @permission_required("IsOwnerOrReadOnly")
    def create_user(  # type: ignore[override]
        self, email: str, password: str, **extra_fields: Any
    ) -> "CustomUser":
        """
        Create and save a user with the given email and password.
        """
        if not email:
            raise ValueError(_("The Email must be set"))
        if not password:
            raise ValueError(_("The Password must be set"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(  # type: ignore[override]
        self, email: str, password: str, **extra_fields: Any
    ) -> "CustomUser":
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self.create_user(email, password, **extra_fields)

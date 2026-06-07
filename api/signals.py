"""Signal handlers for cross-model consistency."""

from __future__ import annotations

import structlog
from allauth.account.models import EmailAddress
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CustomUser

logger = structlog.get_logger(__name__)


@receiver(post_save, sender=CustomUser)
def sync_user_email_address(sender, instance: CustomUser, created: bool, **kwargs) -> None:
    """Keep allauth EmailAddress aligned with CustomUser.email.

    This guarantees that allauth's email metadata (primary, verified)
    always references the current user email after creations and updates,
    regardless of whether the write comes from admin, API, or scripts.

    Parameters
    ----------
    sender:
        The model class that sent the signal.
    instance:
        The saved user instance.
    created:
        Whether the row was created during this save.
    kwargs:
        Extra signal arguments.
    """
    del sender, kwargs

    if not instance.email:
        return

    # allauth's registration flow calls setup_user_email() right after user
    # creation and expects no EmailAddress row to exist yet.
    if created:
        return

    try:
        # Reuse the row that already matches user.email when present.
        email_address = (
            EmailAddress.objects.filter(user=instance, email=instance.email)
            .order_by("-primary", "-verified", "id")
            .first()
        )

        if email_address is None:
            # Otherwise update the current canonical row to the new address.
            email_address = EmailAddress.objects.filter(user=instance).order_by("-primary", "-verified", "id").first()

            if email_address is not None:
                email_address.email = instance.email
                email_address.primary = True
                email_address.save(update_fields=["email", "primary"])
            else:
                email_address = EmailAddress.objects.create(
                    user=instance,
                    email=instance.email,
                    primary=True,
                )

        if not email_address.primary:
            email_address.primary = True
            email_address.save(update_fields=["primary"])

        # Keep a single primary address per user.
        EmailAddress.objects.filter(user=instance).exclude(pk=email_address.pk).update(primary=False)

        # Keep a single canonical email row per user.
        EmailAddress.objects.filter(user=instance).exclude(pk=email_address.pk).delete()
    except Exception:
        logger.exception("email_address_sync_failed", user_pk=instance.pk)

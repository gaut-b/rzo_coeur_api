"""Tests for CustomUser <-> allauth EmailAddress synchronization."""

from allauth.account.models import EmailAddress
from django.test import TestCase

from api.models import CustomUser


class EmailAddressSyncSignalsTests(TestCase):
    """Validate automatic EmailAddress synchronization on user saves."""

    def test_user_creation_does_not_precreate_email_address(self) -> None:
        """Creating a user must not pre-create EmailAddress (allauth contract)."""
        user = CustomUser.objects.create_user(
            email="sync-create@test.com",
            password="pass12345",
        )

        self.assertFalse(EmailAddress.objects.filter(user=user).exists())

    def test_first_update_creates_primary_unverified_email_address(self) -> None:
        """First update after creation must create canonical EmailAddress."""
        user = CustomUser.objects.create_user(
            email="sync-first-update@test.com",
            password="pass12345",
            first_name="Before",
        )

        user.first_name = "After"
        user.save(update_fields=["first_name"])

        email_address = EmailAddress.objects.get(user=user, email=user.email)
        self.assertTrue(email_address.primary)
        self.assertFalse(email_address.verified)

    def test_update_without_email_change_preserves_verified(self) -> None:
        """Saving another field must keep EmailAddress verification state."""
        user = CustomUser.objects.create_user(
            email="sync-stable@test.com",
            password="pass12345",
            first_name="Before",
        )
        email_address = EmailAddress.objects.create(
            user=user,
            email=user.email,
            primary=True,
            verified=True,
        )
        email_address.verified = True
        email_address.save(update_fields=["verified"])

        user.first_name = "After"
        user.save(update_fields=["first_name"])

        email_address.refresh_from_db()
        self.assertTrue(email_address.verified)

    def test_email_change_updates_email_address_and_keeps_verification(self) -> None:
        """Changing user.email must keep EmailAddress verification state."""
        user = CustomUser.objects.create_user(
            email="sync-old@test.com",
            password="pass12345",
        )
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            primary=True,
            verified=True,
        )

        user.email = "sync-new@test.com"
        user.save(update_fields=["email"])

        self.assertFalse(EmailAddress.objects.filter(user=user, email="sync-old@test.com").exists())
        synced = EmailAddress.objects.get(user=user, email="sync-new@test.com")
        self.assertTrue(synced.primary)
        self.assertTrue(synced.verified)

    def test_sync_removes_extra_addresses_and_keeps_single_primary(self) -> None:
        """Signal must clean stale rows and keep one primary address."""
        user = CustomUser.objects.create_user(
            email="sync-clean@test.com",
            password="pass12345",
        )
        EmailAddress.objects.create(
            user=user,
            email="legacy@test.com",
            primary=False,
            verified=True,
        )

        user.email = "sync-clean-2@test.com"
        user.save(update_fields=["email"])

        rows = EmailAddress.objects.filter(user=user)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().email, "sync-clean-2@test.com")
        self.assertTrue(rows.first().primary)

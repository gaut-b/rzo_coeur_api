from django.db import migrations


def sync_email_address_with_user_email(apps, schema_editor):
    """Backfill allauth EmailAddress rows from CustomUser.email.

    Ensures each user has exactly one EmailAddress row matching the current
    user email and marked as primary.
    """
    del schema_editor

    custom_user_model = apps.get_model("api", "CustomUser")
    email_address_model = apps.get_model("account", "EmailAddress")

    users = custom_user_model.objects.exclude(email="").exclude(email__isnull=True)
    for user in users.only("id", "email").iterator():
        current_row = (
            email_address_model.objects.filter(user_id=user.id, email=user.email)
            .order_by("-primary", "-verified", "id")
            .first()
        )

        if current_row is None:
            # Existing data is inconsistent: create the canonical row with
            # unverified status for safety.
            current_row = email_address_model.objects.create(
                user_id=user.id,
                email=user.email,
                primary=False,
                verified=False,
            )

        email_address_model.objects.filter(user_id=user.id).exclude(pk=current_row.pk).delete()

        if not current_row.primary:
            current_row.primary = True
            current_row.save(update_fields=["primary"])


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0001_initial"),
        ("api", "0019_alter_article_name_max_length_500"),
    ]

    operations = [
        migrations.RunPython(sync_email_address_with_user_email, migrations.RunPython.noop),
    ]

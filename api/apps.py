from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self) -> None:
        """Register Django signal handlers at app startup."""
        # Import side effects are intentional: they connect signal receivers.
        from . import signals  # noqa: F401

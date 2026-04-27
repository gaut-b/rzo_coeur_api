"""
Management command: reset_e2e_data

Flush the entire database, re-seed E2E fixtures, and create Django sessions
programmatically for every seeded role.  The session keys are printed to
stdout as a JSON object so the Playwright conftest can inject them as
browser cookies without performing real browser logins.

This command is called **before every E2E test** to guarantee complete
isolation: each test starts from a pristine DB state with no leftover
carts, article assignments or extra users from previous tests.

Safety guard
------------
The command refuses to run unless BOTH conditions are met:
  1. ``settings.DEBUG`` is True (rules out production deployments).
  2. The ``E2E_RESET_CONFIRM=1`` environment variable is set (explicit
     opt-in required in the container that runs E2E tests).

Either condition alone is insufficient: DEBUG can accidentally be True in
a shared staging environment, and the env-var alone could be set by mistake
in a non-E2E context.  Both together create an unambiguous signal.

Usage (inside the E2E backend container):
    E2E_RESET_CONFIRM=1 python manage.py reset_e2e_data
"""

import json
import os

from django.conf import settings
from django.contrib.auth import (
    BACKEND_SESSION_KEY,
    HASH_SESSION_KEY,
    SESSION_KEY,
)
from django.contrib.sessions.backends.db import SessionStore
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from api.models import CustomUser

# Role → email mapping.  Must match the users seeded by seed_data --env e2e.
ROLE_EMAILS: dict[str, str] = {
    "social_admin": "e2e-social-admin@test.local",
    "social_worker": "e2e-social-worker@test.local",
    "shop_manager": "e2e-shop-manager@test.local",
    "cashier": "e2e-cashier@test.local",
    "staff": "e2e-staff@test.local",
}


class Command(BaseCommand):
    """Flush DB, re-seed E2E data, and output JSON session keys."""

    help = (
        "Reset the database for E2E testing: flush all tables, "
        "re-seed fixtures, and create authenticated sessions. "
        "Requires DEBUG=True and E2E_RESET_CONFIRM=1."
    )

    def handle(self, *args: object, **options: object) -> None:
        """Execute flush, seed, and session creation."""
        # Safety guard: refuse to run outside an explicit E2E context.
        if not settings.DEBUG:
            raise CommandError(
                "reset_e2e_data refused: settings.DEBUG is False. "
                "This command must only run against a DEBUG=True instance."
            )
        if os.environ.get("E2E_RESET_CONFIRM") != "1":
            raise CommandError(
                "reset_e2e_data refused: E2E_RESET_CONFIRM is not set to '1'. "
                "Export E2E_RESET_CONFIRM=1 to confirm you intend to wipe "
                "this database."
            )

        # 1. Wipe all data (tables are preserved, rows deleted).
        call_command("flush", verbosity=0, interactive=False)

        # 2. Re-create the canonical E2E fixtures.
        call_command("seed_data", "--env", "e2e", verbosity=0)

        # 3. Create a Django session for each role and collect keys.
        # Use the first configured backend so sessions stay valid if the
        # project's AUTHENTICATION_BACKENDS setting changes.
        auth_backend: str = settings.AUTHENTICATION_BACKENDS[0]
        sessions: dict[str, str] = {}
        for role, email in ROLE_EMAILS.items():
            user = CustomUser.objects.get(email=email)
            session = SessionStore()
            session[SESSION_KEY] = str(user.pk)
            session[BACKEND_SESSION_KEY] = auth_backend
            session[HASH_SESSION_KEY] = user.get_session_auth_hash()
            session.create()
            sessions[role] = session.session_key

        # 4. Print the JSON mapping to stdout so conftest can parse it.
        #    Use self.stdout (Django's management stdout) which is captured
        #    by subprocess in the test runner.
        self.stdout.write(json.dumps(sessions))

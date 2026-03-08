"""
conftest.py — Playwright E2E fixtures for the Django admin test suite.

Provides:
  - django_server: session-scoped fixture that builds and starts the complete
    application stack (nginx + backend/gunicorn + PostGIS + MinIO) via
    docker-compose.e2e.yml, seeds E2E data, and tears everything down (with
    volume removal) at the end of the session.  Skipped when
    E2E_EXTERNAL_STACK=1 (CI mode where the stack is provided externally).
  - Authenticated page fixtures for each role (social_admin, social_worker,
    shop_manager, cashier). Each re-uses a stored browser-context state so
    the login round-trip only happens once per session.

Environment variables (with defaults suitable for local dev):
  E2E_BASE_URL            http://127.0.0.1:8001
  E2E_EXTERNAL_STACK      set to "1" to skip Docker lifecycle (CI mode)
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page

# ─── Constants ────────────────────────────────────────────────────────────────

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8001")
AUTH_DIR = os.path.join(os.path.dirname(__file__), ".auth")
os.makedirs(AUTH_DIR, exist_ok=True)

# Absolute path to the e2e docker-compose file (one level up from this file).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E2E_COMPOSE_FILE = os.path.join(_REPO_ROOT, "docker-compose.e2e.yml")

E2E_PASSWORD = "E2eTestPass123!"

USERS = {
    "social_admin": "e2e-social-admin@test.local",
    "social_worker": "e2e-social-worker@test.local",
    "shop_manager": "e2e-shop-manager@test.local",
    "cashier": "e2e-cashier@test.local",
    "staff": "e2e-staff@test.local",
}

# Each role logs into its "home" admin site for the auth-setup step.
LOGIN_URLS: dict[str, str] = {
    "social_admin": f"{BASE_URL}/social-admin/login/",
    "social_worker": f"{BASE_URL}/cart-admin/login/",
    "shop_manager": f"{BASE_URL}/shop-admin/login/",
    "cashier": f"{BASE_URL}/shop-admin/login/",
    "staff": f"{BASE_URL}/admin/login/",
}


# ─── Stack management ────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def django_server() -> Generator[str, None, None]:
    """
    Build and start the full application stack, seed E2E data, then tear
    everything down at the end of the session.

    The stack is defined in docker-compose.e2e.yml and mirrors production:
    nginx + backend (gunicorn) + PostGIS + MinIO.  docker compose --wait
    blocks until every healthcheck passes, so the server is guaranteed to be
    ready before any test runs.

    Set E2E_EXTERNAL_STACK=1 to skip the Docker lifecycle entirely (CI mode
    where the stack is already running).
    """
    if os.environ.get("E2E_EXTERNAL_STACK") != "1":
        # Start the main stack (db, backend, nginx, minio) and wait for all
        # healthchecks to pass.  minio-init is in the 'init' profile so it
        # is excluded from --wait (it exits 0 which would otherwise cause
        # --wait to return a non-zero exit code).
        compose_up = ["docker", "compose", "-f", E2E_COMPOSE_FILE, "up", "-d"]
        if os.environ.get("E2E_NO_BUILD") != "1":
            compose_up.append("--build")
        compose_up.append("--wait")
        subprocess.run(compose_up, check=True)
        # Run the MinIO bucket initialisation separately.
        subprocess.run(
            ["docker", "compose", "-f", E2E_COMPOSE_FILE, "--profile", "init", "run", "--rm", "minio-init"],
            check=True,
        )

    # Seed test data inside the running backend container (idempotent).
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            E2E_COMPOSE_FILE,
            "exec",
            "backend",
            "python",
            "manage.py",
            "seed_data",
            "--env",
            "e2e",
        ],
        check=True,
    )

    yield BASE_URL

    if os.environ.get("E2E_EXTERNAL_STACK") != "1":
        subprocess.run(
            ["docker", "compose", "-f", E2E_COMPOSE_FILE, "down", "-v"],
            check=True,
        )


# ─── Auth-state helpers ───────────────────────────────────────────────────────


def _auth_state_path(role: str) -> str:
    """Return the path to the stored browser-context state for a role."""
    return os.path.join(AUTH_DIR, f"{role}.json")


def _login_and_save(browser: Browser, role: str, email: str, login_url: str) -> None:
    """
    Perform a real browser login for the given role and persist the session
    state to disk so subsequent fixtures can restore it without re-logging in.
    """
    context = browser.new_context()
    page = context.new_page()
    page.goto(login_url)
    page.locator("#id_username").fill(email)
    page.locator("#id_password").fill(E2E_PASSWORD)
    page.locator('[type="submit"]').click()
    # Wait until we're past the login page (redirected to admin index).
    page.wait_for_url(lambda url: "/login/" not in url and "admin" in url, timeout=10_000)
    context.storage_state(path=_auth_state_path(role))
    context.close()


@pytest.fixture(scope="session")
def authenticated_states(django_server: str, browser: Browser) -> dict[str, str]:
    """
    Session-scoped fixture that logs in once per role and caches the browser
    storage state.  Returns a mapping of role → state-file path.
    """
    states: dict[str, str] = {}
    for role, email in USERS.items():
        state_path = _auth_state_path(role)
        _login_and_save(browser, role, email, LOGIN_URLS[role])
        states[role] = state_path
    return states


# ─── Per-role page fixtures ───────────────────────────────────────────────────


def _make_authed_page(browser: Browser, state_path: str) -> tuple[BrowserContext, Page]:
    """Create a browser context with the saved session state."""
    context = browser.new_context(storage_state=state_path)
    page = context.new_page()
    return context, page


@pytest.fixture
def social_admin_page(browser: Browser, authenticated_states: dict[str, str]) -> Generator[Page, None, None]:
    """Authenticated page for the social admin role."""
    context, page = _make_authed_page(browser, authenticated_states["social_admin"])
    yield page
    context.close()


@pytest.fixture
def cart_admin_page(browser: Browser, authenticated_states: dict[str, str]) -> Generator[Page, None, None]:
    """Authenticated page for the social worker role."""
    context, page = _make_authed_page(browser, authenticated_states["social_worker"])
    yield page
    context.close()


@pytest.fixture
def shop_manager_page(browser: Browser, authenticated_states: dict[str, str]) -> Generator[Page, None, None]:
    """Authenticated page for the shop manager role."""
    context, page = _make_authed_page(browser, authenticated_states["shop_manager"])
    yield page
    context.close()


@pytest.fixture
def cashier_page(browser: Browser, authenticated_states: dict[str, str]) -> Generator[Page, None, None]:
    """Authenticated page for the regular cashier role."""
    context, page = _make_authed_page(browser, authenticated_states["cashier"])
    yield page
    context.close()


@pytest.fixture
def staff_page(browser: Browser, authenticated_states: dict[str, str]) -> Generator[Page, None, None]:
    """Authenticated page for the staff role."""
    context, page = _make_authed_page(browser, authenticated_states["staff"])
    yield page
    context.close()


@pytest.fixture
def anon_page(browser: Browser) -> Generator[Page, None, None]:
    """Unauthenticated browser page."""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()

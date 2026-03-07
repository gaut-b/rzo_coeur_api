"""
conftest.py — Playwright E2E fixtures for the Django admin test suite.

Provides:
  - django_server: session-scoped fixture that starts the Django dev server
    and seeds E2E data before the test session begins.
  - Authenticated page fixtures for each role (social_admin, social_worker,
    shop_manager, cashier). Each re-uses a stored browser-context state so
    the login round-trip only happens once per session.

Environment variables (with defaults suitable for local dev):
  E2E_BASE_URL      http://127.0.0.1:8000
  DJANGO_SETTINGS_MODULE  config.settings
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from collections.abc import Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page

# ─── Constants ────────────────────────────────────────────────────────────────

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8000")
AUTH_DIR = os.path.join(os.path.dirname(__file__), ".auth")
os.makedirs(AUTH_DIR, exist_ok=True)

E2E_PASSWORD = "E2eTestPass123!"

USERS = {
    "social_admin": "e2e-social-admin@test.local",
    "social_worker": "e2e-social-worker@test.local",
    "shop_manager": "e2e-shop-manager@test.local",
    "cashier": "e2e-cashier@test.local",
}

# Each role logs into its "home" admin site for the auth-setup step.
LOGIN_URLS: dict[str, str] = {
    "social_admin": f"{BASE_URL}/social-admin/login/",
    "social_worker": f"{BASE_URL}/cart-admin/login/",
    "shop_manager": f"{BASE_URL}/shop-admin/login/",
    "cashier": f"{BASE_URL}/shop-admin/login/",
}


# ─── Server management ────────────────────────────────────────────────────────


def _wait_for_port(host: str, port: int, timeout: float = 30.0) -> None:
    """Block until the given TCP port is accepting connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Server at {host}:{port} did not start within {timeout}s")


@pytest.fixture(scope="session")
def django_server() -> Generator[str, None, None]:
    """
    Start the Django development server and seed E2E data.

    When the E2E_BASE_URL env var points to an already-running server
    (e.g. in CI where the server is started separately), we skip launching
    a new process and only run the seed command.

    Yields the base URL string.
    """
    host = "127.0.0.1"
    port = 8000
    server_process: subprocess.Popen | None = None

    # Try to connect to an already-running server first.
    already_running = False
    try:
        with socket.create_connection((host, port), timeout=1):
            already_running = True
    except OSError:
        pass

    if not already_running:
        env = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings"),
        }
        server_process = subprocess.Popen(
            [
                "uv",
                "run",
                "python",
                "manage.py",
                "runserver",
                f"{host}:{port}",
                "--noreload",
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _wait_for_port(host, port)

    # Seed test data (idempotent — safe to call every run).
    seed_env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings"),
    }
    subprocess.run(
        ["uv", "run", "python", "manage.py", "seed_data", "--env", "e2e"],
        env=seed_env,
        check=True,
    )

    yield BASE_URL

    if server_process is not None:
        server_process.terminate()
        server_process.wait(timeout=10)


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
def social_worker_page(browser: Browser, authenticated_states: dict[str, str]) -> Generator[Page, None, None]:
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
def anon_page(browser: Browser) -> Generator[Page, None, None]:
    """Unauthenticated browser page."""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()

"""
conftest.py — Playwright E2E fixtures for the Django admin test suite.

Provides:
  - django_server: session-scoped fixture that builds and starts the complete
    application stack (nginx + backend/gunicorn + PostGIS + MinIO) via
    docker-compose.e2e.yml, and tears everything down (with volume removal)
    at the end of the session.  Skipped when E2E_EXTERNAL_STACK=1 (CI mode
    where the stack is provided externally).
  - reset_db: function-scoped autouse fixture that flushes the database,
    re-seeds E2E data, creates Django sessions for each role, clears
    Mailhog, and writes browser-state files so per-role page fixtures
    can restore authenticated contexts without a real browser login.
  - Authenticated page fixtures for each role (social_admin, social_worker,
    shop_manager, cashier, staff).
  - anon_page: unauthenticated browser page for login / access-denied tests.

Environment variables (with defaults suitable for local dev):
  E2E_BASE_URL            http://127.0.0.1:8001
  E2E_EXTERNAL_STACK      set to "1" to skip Docker lifecycle (CI mode)
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Generator
from urllib.parse import urlparse

import pytest
import requests
from playwright.sync_api import Browser, BrowserContext, Page

# ─── Constants ────────────────────────────────────────────────────────────────

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8001")
MAILHOG_API_URL = os.environ.get("E2E_MAILHOG_URL", "http://localhost:8025")
AUTH_DIR = os.path.join(os.path.dirname(__file__), ".auth")
os.makedirs(AUTH_DIR, exist_ok=True)

# Absolute path to the e2e docker-compose file (one level up from this file).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E2E_COMPOSE_FILE = os.path.join(_REPO_ROOT, "docker-compose.e2e.yml")

E2E_PASSWORD = "E2eTestPass123!"


def _auth_state_path(role: str) -> str:
    """Return the path to the stored browser-context state for a role."""
    return os.path.join(AUTH_DIR, f"{role}.json")


# ─── Stack management ────────────────────────────────────────────────────────


def _wait_for_mailhog(url: str, timeout: float = 30.0) -> None:
    """
    Block until the Mailhog HTTP API is reachable from the host.

    ``docker compose --wait`` checks healthchecks from *inside* each container.
    On macOS with Docker Desktop the TCP port binding on the host side may
    not be ready immediately after the healthcheck passes, causing the first
    ``requests`` call from the test runner to get a ConnectionRefusedError.
    """
    import time

    import requests as _req

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            _req.get(url, timeout=2)
            return
        except _req.exceptions.ConnectionError:
            time.sleep(0.5)
    raise RuntimeError(f"Mailhog HTTP API not accessible at {url!r} after {timeout}s")


@pytest.fixture(scope="session")
def django_server() -> Generator[str, None, None]:
    """
    Build and start the full application stack, then tear everything down
    at the end of the session.

    The stack is defined in docker-compose.e2e.yml and mirrors production:
    nginx + backend (gunicorn) + PostGIS + MinIO.  docker compose --wait
    blocks until every healthcheck passes, so the server is guaranteed to be
    ready before any test runs.

    Database seeding is NOT done here — the function-scoped ``reset_db``
    fixture flushes and re-seeds the DB before every test to guarantee
    complete isolation.

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
        # On macOS with Docker Desktop the host-side port binding may lag
        # behind the container healthcheck.  Poll until localhost:8025 is up.
        _wait_for_mailhog(f"{MAILHOG_API_URL}/api/v2/messages")
        # Run the MinIO bucket initialisation separately.
        subprocess.run(
            ["docker", "compose", "-f", E2E_COMPOSE_FILE, "--profile", "init", "run", "--rm", "minio-init"],
            check=True,
        )

    yield BASE_URL

    if os.environ.get("E2E_EXTERNAL_STACK") != "1":
        subprocess.run(
            ["docker", "compose", "-f", E2E_COMPOSE_FILE, "down", "-v"],
            check=True,
        )


# ─── DB reset & session injection ─────────────────────────────────────────────

# Roles that need an authenticated browser context.
_ROLES = ("social_admin", "social_worker", "shop_manager", "cashier", "staff")


def _build_storage_state(session_key: str) -> dict:
    """
    Build a Playwright storage-state dict containing a single ``sessionid``
    cookie for the given Django session key.

    The ``secure`` flag is derived from the URL scheme so the cookie is
    sent correctly whether the E2E stack runs over HTTP (local dev) or
    HTTPS (CI / external stacks with ``E2E_BASE_URL``).
    """
    parsed = urlparse(BASE_URL)
    if not parsed.hostname:
        raise ValueError(
            f"E2E_BASE_URL {BASE_URL!r} has no hostname. Set E2E_BASE_URL to a valid URL (e.g. http://127.0.0.1:8001)."
        )
    return {
        "cookies": [
            {
                "name": "sessionid",
                "value": session_key,
                "domain": parsed.hostname,
                "path": "/",
                "httpOnly": True,
                "secure": parsed.scheme == "https",
                "sameSite": "Lax",
            },
        ],
        "origins": [],
    }


def _write_auth_states(sessions: dict[str, str]) -> dict[str, str]:
    """
    Validate *sessions*, write one ``.auth/<role>.json`` file per role,
    and return a role → file-path mapping.

    Raises ``RuntimeError`` with a human-readable message if the mapping
    returned by ``reset_e2e_data`` is missing expected roles or contains
    unexpected ones, rather than letting later code fail with a bare
    ``KeyError``.
    """
    expected = set(_ROLES)
    received = set(sessions.keys())
    missing = expected - received
    extra = received - expected
    if missing or extra:
        parts: list[str] = []
        if missing:
            parts.append(f"missing roles: {sorted(missing)}")
        if extra:
            parts.append(f"unexpected roles: {sorted(extra)}")
        raise RuntimeError(
            f"reset_e2e_data returned an unexpected session mapping ({'; '.join(parts)}). Got keys: {sorted(received)}"
        )

    paths: dict[str, str] = {}
    for role in _ROLES:
        state = _build_storage_state(sessions[role])
        path = _auth_state_path(role)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        paths[role] = path
    return paths


@pytest.fixture(autouse=True)
def reset_db(django_server: str) -> dict[str, str]:
    """
    Flush the DB, re-seed E2E fixtures, create Django sessions for each
    role, clear Mailhog, and write browser-auth state files.

    Runs **before every test** (function scope, autouse) to guarantee
    complete isolation: no leftover carts, article assignments, extra
    users, or stale emails from previous tests.

    Returns a role → auth-state-file-path mapping used by per-role page
    fixtures.
    """
    # 1. Flush + seed + create sessions inside the backend container.
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            E2E_COMPOSE_FILE,
            "exec",
            "-T",
            "backend",
            "python",
            "manage.py",
            "reset_e2e_data",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    # The command prints a JSON object as its last line on stdout.
    # Preceding lines may contain Django management command output
    # (e.g. from seed_data); only the last line is the JSON payload.
    stdout = result.stdout.strip()
    if not stdout:
        raise RuntimeError(
            "reset_e2e_data produced no stdout; expected a JSON payload on the last line.\n"
            f"stderr:\n{result.stderr.strip() or '(empty)'}"
        )
    last_line = stdout.splitlines()[-1]
    try:
        sessions: dict[str, str] = json.loads(last_line)
    except json.JSONDecodeError as exc:
        tail = "\n".join(stdout.splitlines()[-10:])
        raise RuntimeError(
            f"reset_e2e_data output could not be parsed as JSON: {exc}\n"
            f"Last line received: {last_line!r}\n"
            f"stdout (last 10 lines):\n{tail}\n"
            f"stderr:\n{result.stderr.strip() or '(empty)'}"
        ) from exc

    # 2. Write Playwright browser-state files for each role.
    auth_paths = _write_auth_states(sessions)

    # 3. Clear Mailhog so each test starts with an empty inbox.
    response = requests.delete(f"{MAILHOG_API_URL}/api/v1/messages", timeout=5)
    response.raise_for_status()

    return auth_paths


# ─── Per-role page fixtures ───────────────────────────────────────────────────


def _make_authed_page(browser: Browser, state_path: str) -> tuple[BrowserContext, Page]:
    """Create a browser context with the saved session state."""
    context = browser.new_context(storage_state=state_path)
    page = context.new_page()
    return context, page


@pytest.fixture
def staff_page(browser: Browser, reset_db: dict[str, str]) -> Generator[Page, None, None]:
    """Authenticated page for the staff role."""
    context, page = _make_authed_page(browser, reset_db["staff"])
    yield page
    context.close()


@pytest.fixture
def social_admin_page(browser: Browser, reset_db: dict[str, str]) -> Generator[Page, None, None]:
    """Authenticated page for the social admin role."""
    context, page = _make_authed_page(browser, reset_db["social_admin"])
    yield page
    context.close()


@pytest.fixture
def cart_admin_page(browser: Browser, reset_db: dict[str, str]) -> Generator[Page, None, None]:
    """Authenticated page for the social worker role."""
    context, page = _make_authed_page(browser, reset_db["social_worker"])
    yield page
    context.close()


@pytest.fixture
def shop_manager_page(browser: Browser, reset_db: dict[str, str]) -> Generator[Page, None, None]:
    """Authenticated page for the shop manager role."""
    context, page = _make_authed_page(browser, reset_db["shop_manager"])
    yield page
    context.close()


@pytest.fixture
def cashier_page(browser: Browser, reset_db: dict[str, str]) -> Generator[Page, None, None]:
    """Authenticated page for the regular cashier role."""
    context, page = _make_authed_page(browser, reset_db["cashier"])
    yield page
    context.close()


@pytest.fixture
def anon_page(browser: Browser) -> Generator[Page, None, None]:
    """Unauthenticated browser page."""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()

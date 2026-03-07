"""
Management command: seed_data

Creates an idempotent set of fixtures used either for local development or
for Playwright E2E tests, depending on the --env option.

Fixture data is loaded from JSON files in api/fixtures/<env>/ — one file per
entity type. References between entities use lookup fields (names or emails)
rather than PKs, so the JSON files are human-readable and easy to extend.

Supported environments:
    dev   — realistic development data (default)
    e2e   — minimal data used by Playwright tests

Usage:
    uv run python manage.py seed_data             # dev fixtures
    uv run python manage.py seed_data --env e2e   # E2E test fixtures
"""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from api.models import (
    Article,
    Cashier,
    Client,
    CustomUser,
    Recipient,
    Shop,
    SocialCenter,
    SocialWorker,
)

# All E2E and dev test users share the same password — kept in code, not in
# JSON fixtures, so it is never accidentally committed to a less-controlled
# location.
SEED_PASSWORD = "E2eTestPass123!"

FIXTURES_BASE_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"

SUPPORTED_ENVS = ("dev", "e2e")


class Command(BaseCommand):
    """Seed the database with fixtures for development or E2E testing."""

    help = "Seed the database with fixtures (idempotent). " "Use --env to choose between 'dev' (default) and 'e2e'."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register the --env argument."""
        parser.add_argument(
            "--env",
            choices=SUPPORTED_ENVS,
            default="dev",
            help=(
                "Fixture environment to load: "
                "'dev' for development data (default), "
                "'e2e' for Playwright E2E test data."
            ),
        )

    def handle(self, *args: object, **options: object) -> None:
        """Load fixture files and create all objects in dependency order."""
        env: str = options["env"]  # type: ignore[assignment]
        self.fixtures_dir = FIXTURES_BASE_DIR / env

        self.stdout.write(f"Seeding '{env}' data from {self.fixtures_dir}...")

        social_centers = self._seed_social_centers()
        shops = self._seed_shops(social_centers)
        self._seed_social_workers(social_centers)
        self._seed_cashiers(shops)
        self._seed_recipients(social_centers)
        clients = self._seed_clients()
        self._seed_articles(shops, clients)

        self.stdout.write(self.style.SUCCESS(f"'{env}' seed data ready."))

    # ─── Fixture loader ───────────────────────────────────────────────────────

    def _load_fixture(self, filename: str) -> list[dict[str, Any]]:
        """Load and return parsed JSON from a fixture file."""
        path = self.fixtures_dir / filename
        with path.open(encoding="utf-8") as f:
            return json.load(f)  # type: ignore[no-any-return]

    # ─── User helper ──────────────────────────────────────────────────────────

    def _get_or_create_user(
        self,
        email: str,
        first_name: str,
        last_name: str,
    ) -> CustomUser:
        """
        Return an existing user by email, or create a new one with SEED_PASSWORD.

        Password is always reset so local DB changes don't break tests.
        """
        user, _ = CustomUser.objects.get_or_create(
            email=email,
            defaults={"first_name": first_name, "last_name": last_name},
        )
        user.set_password(SEED_PASSWORD)
        user.save(update_fields=["password"])
        return user

    # ─── Seeders (one per entity type) ───────────────────────────────────────

    def _seed_social_centers(self) -> dict[str, SocialCenter]:
        """Create social centers; return a name→instance mapping."""
        centers: dict[str, SocialCenter] = {}
        for data in self._load_fixture("social_centers.json"):
            center, _ = SocialCenter.objects.get_or_create(
                name=data["name"],
                defaults={"mail": data["mail"]},
            )
            centers[center.name] = center
            self.stdout.write(f"  Social Center : {center.name}")
        return centers

    def _seed_shops(self, social_centers: dict[str, SocialCenter]) -> dict[str, Shop]:
        """Create shops; return a name→instance mapping."""
        shops: dict[str, Shop] = {}
        for data in self._load_fixture("shops.json"):
            social_center = social_centers[data["social_center"]]
            shop, _ = Shop.objects.get_or_create(
                name=data["name"],
                defaults={"social_center": social_center},
            )
            if shop.social_center != social_center:
                shop.social_center = social_center
                shop.save(update_fields=["social_center"])
            shops[shop.name] = shop
            self.stdout.write(f"  Shop          : {shop.name}")
        return shops

    def _seed_social_workers(self, social_centers: dict[str, SocialCenter]) -> None:
        """Create social worker / social admin users."""
        for data in self._load_fixture("social_workers.json"):
            social_center = social_centers[data["social_center"]]
            user = self._get_or_create_user(data["email"], data["first_name"], data["last_name"])
            is_admin: bool = data.get("is_social_admin", False)
            sw, _ = SocialWorker.objects.get_or_create(
                user=user,
                defaults={
                    "social_center": social_center,
                    "is_social_admin": is_admin,
                },
            )
            if sw.is_social_admin != is_admin or sw.social_center != social_center:
                sw.is_social_admin = is_admin
                sw.social_center = social_center
                sw.save(update_fields=["is_social_admin", "social_center"])
            self.stdout.write(f"  Social Worker : {user.email}")

    def _seed_cashiers(self, shops: dict[str, Shop]) -> None:
        """Create cashier / shop manager users."""
        for data in self._load_fixture("cashiers.json"):
            shop = shops[data["shop"]]
            user = self._get_or_create_user(data["email"], data["first_name"], data["last_name"])
            is_manager: bool = data.get("is_shop_manager", False)
            cashier, _ = Cashier.objects.get_or_create(
                user=user,
                defaults={"shop": shop, "is_shop_manager": is_manager},
            )
            if cashier.is_shop_manager != is_manager or cashier.shop != shop:
                cashier.is_shop_manager = is_manager
                cashier.shop = shop
                cashier.save(update_fields=["is_shop_manager", "shop"])
            self.stdout.write(f"  Cashier       : {user.email}")

    def _seed_recipients(self, social_centers: dict[str, SocialCenter]) -> None:
        """Create recipient users."""
        for data in self._load_fixture("recipients.json"):
            social_center = social_centers[data["social_center"]]
            user = self._get_or_create_user(data["email"], data["first_name"], data["last_name"])
            recipient, _ = Recipient.objects.get_or_create(
                user=user,
                defaults={"social_center": social_center},
            )
            if recipient.social_center != social_center:
                recipient.social_center = social_center
                recipient.save(update_fields=["social_center"])
            self.stdout.write(f"  Recipient     : {user.email}")

    def _seed_clients(self) -> dict[str, Client]:
        """Create client users; return an email→Client instance mapping."""
        clients: dict[str, Client] = {}
        for data in self._load_fixture("clients.json"):
            user = self._get_or_create_user(data["email"], data["first_name"], data["last_name"])
            client, _ = Client.objects.get_or_create(user=user)
            clients[user.email] = client
        return clients

    def _seed_articles(self, shops: dict[str, Shop], clients: dict[str, Client]) -> None:
        """
        Create articles from fixture file.

        Always resets cart=None so articles are available at the start of each
        test run or fresh dev session, regardless of what previous runs did.
        """
        for data in self._load_fixture("articles.json"):
            shop = shops[data["shop"]]
            client = clients[data["client"]]
            article, _ = Article.objects.get_or_create(
                barcode=data["barcode"],
                shop=shop,
                defaults={
                    "client": client,
                    "name": data["name"],
                    "brand_label": data["brand_label"],
                    "cart": None,
                },
            )
            if article.cart is not None:
                article.cart = None
                article.save(update_fields=["cart"])

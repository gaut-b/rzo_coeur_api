"""
Tests for the photo upload endpoint.

These tests cover:
- POST /api/articles/photos/ (ArticlePhotoUploadView)

The photo upload tests mock ``default_storage`` so that they can run
without a live MinIO instance.
"""

import io
from unittest.mock import MagicMock, patch

from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Cashier, Client, CustomUser, Shop, SocialCenter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_client_user(email: str = "client@test.com") -> tuple[CustomUser, Client]:
    """Create and return a CustomUser with Client role."""
    user: CustomUser = CustomUser.objects.create_user(  # type: ignore[attr-defined]
        email=email,
        password="SecurePass123!",
        first_name="Client",
        last_name="Test",
    )
    client = Client.objects.create(user=user)
    return user, client


def _create_cashier_user(shop: Shop, email: str = "cashier@test.com") -> tuple[CustomUser, Cashier]:
    """Create and return a CustomUser with Cashier role linked to *shop*."""
    user: CustomUser = CustomUser.objects.create_user(  # type: ignore[attr-defined]
        email=email,
        password="SecurePass123!",
        first_name="Caissier",
        last_name="Test",
    )
    cashier = Cashier.objects.create(user=user, shop=shop)
    return user, cashier


def _make_image_file(
    fmt: str = "JPEG",
    content_type: str = "image/jpeg",
    name: str = "photo.jpg",
    size_kb: int = 10,
) -> "io.BytesIO":
    """
    Generate a minimal in-memory image file suitable for multipart upload.

    Parameters:
        fmt: Pillow format string (JPEG, PNG, WEBP).
        content_type: MIME type string attached to the file object.
        name: Filename attribute used by Django's parser.
        size_kb: Approximate target size (not exact — Pillow compresses).

    Returns:
        BytesIO buffer with ``name`` and ``content_type`` attributes set.
    """
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    buf.name = name
    buf.content_type = content_type  # type: ignore[attr-defined]
    return buf


# ---------------------------------------------------------------------------
# ArticlePhotoUploadView tests
# ---------------------------------------------------------------------------


class ArticlePhotoUploadViewTests(APITestCase):
    """Tests for POST /api/articles/photos/."""

    URL = "/api/articles/photos/"

    def setUp(self) -> None:
        """Create a client user for authenticated requests."""
        self.client_user, _ = _create_client_user()

    # ── happy path ───────────────────────────────────────────────────────────

    @patch("api.views.default_storage")
    def test_valid_jpeg_returns_201_with_url(self, mock_storage: MagicMock) -> None:
        """201 response with URL when a valid JPEG is uploaded."""
        mock_storage.save.return_value = "articles/abc123.jpg"
        mock_storage.url.return_value = "http://localhost:9000/articles-photos/articles/abc123.jpg"

        self.client.force_authenticate(user=self.client_user)
        image = _make_image_file(fmt="JPEG", content_type="image/jpeg", name="photo.jpg")
        response = self.client.post(self.URL, {"image": image}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("url", response.data)
        self.assertEqual(response.data["url"], "http://localhost:9000/articles-photos/articles/abc123.jpg")
        mock_storage.save.assert_called_once()

    @patch("api.views.default_storage")
    def test_valid_png_returns_201(self, mock_storage: MagicMock) -> None:
        """201 response for a valid PNG upload."""
        mock_storage.save.return_value = "articles/abc456.png"
        mock_storage.url.return_value = "http://localhost:9000/articles-photos/articles/abc456.png"

        self.client.force_authenticate(user=self.client_user)
        image = _make_image_file(fmt="PNG", content_type="image/png", name="photo.png")
        response = self.client.post(self.URL, {"image": image}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("url", response.data)

    @patch("api.views.default_storage")
    def test_valid_webp_returns_201(self, mock_storage: MagicMock) -> None:
        """201 response for a valid WebP upload."""
        mock_storage.save.return_value = "articles/abc789.webp"
        mock_storage.url.return_value = "http://localhost:9000/articles-photos/articles/abc789.webp"

        self.client.force_authenticate(user=self.client_user)
        image = _make_image_file(fmt="WEBP", content_type="image/webp", name="photo.webp")
        response = self.client.post(self.URL, {"image": image}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # ── validation errors ────────────────────────────────────────────────────

    def test_missing_image_returns_400(self) -> None:
        """400 when no file is included in the request."""
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post(self.URL, {}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("image", response.data)

    def test_unsupported_content_type_returns_400(self) -> None:
        """400 when the uploaded file has an unsupported content type (e.g. GIF)."""
        self.client.force_authenticate(user=self.client_user)
        # Create a minimal GIF-like buffer (Pillow doesn't need to validate in
        # serializer — we check content_type, not file magic bytes).
        img = Image.new("RGB", (10, 10))
        buf = io.BytesIO()
        img.save(buf, format="GIF")
        buf.seek(0)
        buf.name = "anim.gif"
        buf.content_type = "image/gif"  # type: ignore[attr-defined]

        response = self.client.post(self.URL, {"image": buf}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("image", response.data)

    def test_file_exceeding_size_limit_returns_400(self) -> None:
        """400 when the uploaded file exceeds 5 MB."""
        self.client.force_authenticate(user=self.client_user)

        # Build an oversized fake image: pad with zeros after the image bytes
        img = Image.new("RGB", (10, 10))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")

        # Pad to 6 MB
        buf.write(b"\x00" * (6 * 1024 * 1024))
        buf.seek(0)
        buf.name = "big.jpg"
        buf.content_type = "image/jpeg"  # type: ignore[attr-defined]

        response = self.client.post(self.URL, {"image": buf}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("image", response.data)

    # ── permissions ─────────────────────────────────────────────────────────

    def test_unauthenticated_returns_401(self) -> None:
        """401 when the request carries no credentials."""
        image = _make_image_file()
        response = self.client.post(self.URL, {"image": image}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cashier_returns_403(self) -> None:
        """403 when a Cashier role tries to upload a photo."""
        social_center = SocialCenter.objects.create(
            name="Centre2",
            street_number="3",
            street_name="Bd Test",
            postal_code="75003",
            city="Paris",
            mail="c2@test.com",
        )
        shop = Shop.objects.create(
            name="Shop2",
            street_number="4",
            street_name="Av Test",
            postal_code="75004",
            city="Paris",
            social_center=social_center,
        )
        cashier_user, _ = _create_cashier_user(shop, email="cashier3@test.com")
        self.client.force_authenticate(user=cashier_user)

        image = _make_image_file()
        response = self.client.post(self.URL, {"image": image}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ── filename uniqueness ──────────────────────────────────────────────────

    @patch("api.views.default_storage")
    def test_uploaded_filename_is_uuid_based(self, mock_storage: MagicMock) -> None:
        """The filename passed to storage uses a UUID, not the original name."""
        mock_storage.save.return_value = "articles/someuuid.jpg"
        mock_storage.url.return_value = "http://localhost:9000/articles-photos/articles/someuuid.jpg"

        self.client.force_authenticate(user=self.client_user)
        image = _make_image_file(name="my_personal_photo_2026.jpg")
        self.client.post(self.URL, {"image": image}, format="multipart")

        saved_name: str = mock_storage.save.call_args[0][0]
        # Should be "articles/<32 hex chars>.jpg"
        self.assertTrue(saved_name.startswith("articles/"))
        self.assertNotIn("my_personal_photo_2026", saved_name)

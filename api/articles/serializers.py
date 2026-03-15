from rest_framework import serializers

from api.constants import MAX_ARTICLES_PER_REQUEST
from api.enums import UserRole
from api.models import Article, Client


class ArticleInputSerializer(serializers.Serializer):
    """
    Serializer for individual article input with barcode.
    Used as part of bulk article creation.
    """

    barcode = serializers.IntegerField(
        min_value=0,
        help_text="EAN-13 or similar product barcode (numeric only)",
    )
    name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    img_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    thumb_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    brand_label = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ArticleSerializer(serializers.ModelSerializer):
    """Serializer for Article model output."""

    class Meta:
        model = Article
        fields = [
            "id",
            "name",
            "barcode",
            "client",
            "shop",
            "cart",
            "img_url",
            "thumb_url",
            "brand_label",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ArticleDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed article output with shop info, cart info, and status.
    Used for client's article list view.
    """

    shop = serializers.SerializerMethodField()
    cart = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            "id",
            "barcode",
            "name",
            "img_url",
            "thumb_url",
            "brand_label",
            "shop",
            "status",
            "cart",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_shop(self, obj) -> dict:
        """Return shop information."""
        return {
            "id": obj.shop.id,
            "name": obj.shop.name,
        }

    def get_cart(self, obj) -> dict | None:
        """Return cart information if article is assigned to a cart."""
        if obj.cart:
            return {
                "id": obj.cart.id,
                "status": obj.cart.status,
            }
        return None

    def get_status(self, obj) -> str:
        """
        Calculate article status based on cart assignment.
        - AVAILABLE: No cart assigned
        - ASSIGNED or COLLECTED: Based on cart status
        """
        if not obj.cart:
            return "AVAILABLE"
        return obj.cart.status


class ArticleCartSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for articles within a cart context.
    Only returns essential article information (id, barcode, name).
    Shop, status, and cart info are already available at the cart level.
    """

    class Meta:
        model = Article
        fields = ["id", "barcode", "name", "img_url", "thumb_url", "brand_label"]
        read_only_fields = ["id"]


class BulkArticleCreateSerializer(serializers.Serializer):
    """
    Serializer for bulk article creation.
    Validates client_id and articles list.
    The shop_id is automatically retrieved from the authenticated cashier user.

    Used by cashiers when scanning multiple articles for a client.
    Maximum number of articles per request is configurable via
    MAX_ARTICLES_PER_REQUEST. Default to 10.
    """

    client_id = serializers.IntegerField(help_text="ID of the client user (must have CLIENT role)")
    articles = ArticleInputSerializer(
        many=True,
        help_text=(f"List of articles to create (maximum {MAX_ARTICLES_PER_REQUEST} per request)"),
    )

    def validate_articles(self, value):
        """
        Validate that the articles list is not empty and doesn't exceed the
        configured maximum.
        """
        if not value:
            raise serializers.ValidationError("Articles list cannot be empty.")
        if len(value) > MAX_ARTICLES_PER_REQUEST:
            raise serializers.ValidationError(
                f"Cannot create more than {MAX_ARTICLES_PER_REQUEST} articles at "
                f"once. Received {len(value)} articles. Please reduce the batch "
                "size."
            )
        return value

    def validate_client_id(self, value):
        """
        Validate that client_id exists and corresponds to a Client user.
        Caches the client instance to avoid duplicate DB query in create().
        """
        try:
            client = Client.objects.select_related("user").get(pk=value)
        except Client.DoesNotExist:
            raise serializers.ValidationError(f"Client with id {value} does not exist.")

        # Verify that the user has the CLIENT role
        if client.user.role != UserRole.CLIENT.value:
            raise serializers.ValidationError(f"User with id {value} is not a Client.")

        # Cache the client to avoid duplicate query in create()
        self._validated_client = client

        return value

    def validate(self, attrs):
        """
        Object-level validation.
        Validates that the authenticated cashier has an associated shop.
        Caches the shop instance for use in create().
        """
        request = self.context.get("request")
        if request is None:
            raise serializers.ValidationError("Request context is required.")
        cashier = getattr(request.user, "cashier", None)
        shop = getattr(cashier, "shop", None)

        if shop is None:
            raise serializers.ValidationError("Authenticated user does not have an associated shop.")

        # Cache the shop to avoid duplicate access in create()
        self._validated_shop = shop

        return attrs

    def create(self, validated_data):
        """
        Create multiple articles in bulk.
        The shop is automatically retrieved from the authenticated cashier user.
        """
        articles_data = validated_data["articles"]

        # Reuse cached client from validation to avoid duplicate DB query
        client = getattr(self, "_validated_client", None)
        if client is None:
            # Fallback if validation was bypassed (shouldn't happen in normal flow)
            client = Client.objects.get(pk=validated_data["client_id"])

        # Reuse cached shop from validation
        shop = getattr(self, "_validated_shop", None)

        # Prepare article objects for bulk creation
        articles_to_create = [
            Article(
                name=article_data.get("name", ""),
                barcode=article_data["barcode"],
                client=client,
                shop=shop,
                cart=None,  # Articles are created without cart assignment
                img_url=article_data.get("img_url", ""),
                thumb_url=article_data.get("thumb_url", ""),
                brand_label=article_data.get("brand_label", ""),
            )
            for article_data in articles_data
        ]

        # Bulk create articles
        created_articles = Article.objects.bulk_create(articles_to_create)

        return created_articles


class PhotoUploadSerializer(serializers.Serializer):
    """
    Serializer for article photo uploads.

    Validates that the uploaded file is an image of an accepted MIME type
    (JPEG, PNG, or WebP) and does not exceed the maximum allowed size.
    """

    # 5 MB limit
    MAX_SIZE_BYTES = 5 * 1024 * 1024
    ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

    image = serializers.ImageField(help_text="Image file to upload (JPEG, PNG or WebP, max 5 MB).")

    def validate_image(self, value):
        """
        Validate image MIME type and file size.

        Parameters:
            value: The uploaded InMemoryUploadedFile or TemporaryUploadedFile.

        Returns:
            The validated file if all checks pass.

        Raises:
            serializers.ValidationError: If the file type or size is invalid.
        """
        if value.content_type not in self.ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError(
                f"Unsupported file type '{value.content_type}'. "
                f"Accepted types: {', '.join(sorted(self.ALLOWED_CONTENT_TYPES))}."
            )

        if value.size > self.MAX_SIZE_BYTES:
            max_mb = self.MAX_SIZE_BYTES / (1024 * 1024)
            raise serializers.ValidationError(
                f"File size {value.size / (1024 * 1024):.1f} MB exceeds the {max_mb:.0f} MB limit."
            )

        return value

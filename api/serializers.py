from auth_kit.serializers.user import UserSerializer as AuthKitUserSerializer
from rest_framework import serializers

from .constants import MAX_ARTICLES_PER_REQUEST
from .enums import UserRole
from .models import Article, Client, CustomUser


class CustomUserSerializer(AuthKitUserSerializer):
    """
    Custom serializer for CustomUser that extends auth_kit's UserSerializer.
    Adds the 'role' field dynamically calculated from OneToOne relationships.
    """

    role = serializers.ReadOnlyField()

    class Meta(AuthKitUserSerializer.Meta):
        model = CustomUser
        fields = AuthKitUserSerializer.Meta.fields + ("role",)


class ArticleInputSerializer(serializers.Serializer):
    """
    Serializer for individual article input with barcode.
    Used as part of bulk article creation.
    """

    barcode = serializers.IntegerField(
        min_value=0, help_text="EAN-13 or similar product barcode (numeric only)"
    )


class ArticleSerializer(serializers.ModelSerializer):
    """
    Serializer for Article model output.
    """

    class Meta:
        model = Article
        fields = ["id", "name", "barcode", "client", "shop", "cart"]
        read_only_fields = ["id"]


class BulkArticleCreateSerializer(serializers.Serializer):
    """
    Serializer for bulk article creation.
    Validates client_id and articles list.
    The shop_id is automatically retrieved from the authenticated cashier user.

    Used by cashiers when scanning multiple articles for a client.
    Maximum number of articles per request is configurable via MAX_ARTICLES_PER_REQUEST.
    Default to 10.
    """

    client_id = serializers.IntegerField(help_text="ID of the client user (must have CLIENT role)")
    articles = ArticleInputSerializer(
        many=True,
        help_text=f"List of articles to create (maximum {MAX_ARTICLES_PER_REQUEST} per request)",
    )

    def validate_articles(self, value):
        """
        Validate that the articles list is not empty and doesn't exceed the configured maximum.
        """
        if not value:
            raise serializers.ValidationError("Articles list cannot be empty.")
        if len(value) > MAX_ARTICLES_PER_REQUEST:
            raise serializers.ValidationError(
                f"Cannot create more than {MAX_ARTICLES_PER_REQUEST} articles at once. "
                f"Received {len(value)} articles. Please reduce the batch size."
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
        cashier = getattr(request.user, "cashier", None)
        shop = getattr(cashier, "shop", None)

        if shop is None:
            raise serializers.ValidationError(
                "Authenticated user does not have an associated shop."
            )

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
                name="",  # Name left empty for later enrichment
                barcode=article_data["barcode"],
                client=client,
                shop=shop,
                cart=None,  # Articles are created without cart assignment
            )
            for article_data in articles_data
        ]

        # Bulk create articles
        created_articles = Article.objects.bulk_create(articles_to_create)

        return created_articles


class CartSerializer(serializers.ModelSerializer):
    """
    Serializer for Cart model output.
    """

    shop_name = serializers.CharField(source="shop.name", read_only=True)
    recipient_email = serializers.EmailField(source="recipient.user.email", read_only=True)
    recipient_name = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "shop",
            "shop_name",
            "recipient",
            "recipient_email",
            "recipient_name",
            "status",
            "collected_at",
        ]
        read_only_fields = ["id", "collected_at"]

    def get_recipient_name(self, obj):
        """Return the full name of the recipient."""
        user = obj.recipient.user
        return f"{user.first_name} {user.last_name}"


class CartCollectSerializer(serializers.Serializer):
    """
    Serializer for marking a Cart as collected.
    No input fields required - recipient and cart IDs come from URL.
    """

    def validate(self, attrs):
        """
        Validate that:
        - Cart status is ASSIGNED
        - Cashier's shop matches cart's shop
        - Cart belongs to the specified recipient
        """
        request = self.context.get("request")
        cart = self.context.get("cart")
        recipient = self.context.get("recipient")

        if not cart:
            raise serializers.ValidationError("Cart context is required.")
        if not recipient:
            raise serializers.ValidationError("Recipient context is required.")

        if cart.status != CartStatus.ASSIGNED.value:
            raise serializers.ValidationError(
                {
                    "status": (
                        f"Cart must be in ASSIGNED status to be collected. "
                        f"Current status: {cart.status}"
                    )
                }
            )
        cashier = getattr(request.user, "cashier", None)
        if not cashier or cashier.shop != cart.shop:
            raise serializers.ValidationError(
                {"shop": "You can only collect carts from your shop."}
            )

        if cart.recipient != recipient:
            raise serializers.ValidationError(
                {"recipient": "The cart does not belong to this recipient."}
            )

        return attrs

    def update(self, instance, validated_data):
        """Update the cart status to COLLECTED and set collected_at timestamp."""
        from django.utils import timezone

        instance.status = CartStatus.COLLECTED.value
        instance.collected_at = timezone.now()
        instance.save()
        return instance

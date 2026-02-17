from auth_kit.serializers.registration import RegisterSerializer as AuthKitRegisterSerializer
from auth_kit.serializers.user import UserSerializer as AuthKitUserSerializer
from django.utils import timezone
from rest_framework import serializers

from .constants import MAX_ARTICLES_PER_REQUEST
from .enums import CartStatus, UserRole
from .models import Article, Cart, Client, CustomUser, Shop, SocialCenter


class CustomUserSerializer(AuthKitUserSerializer):
    """
    Custom serializer for CustomUser that extends auth_kit's UserSerializer.
    Adds the 'role' field dynamically calculated from OneToOne relationships.
    Maps roles for frontend compatibility:
    - CLIENT, RECIPIENT, CASHIER → unchanged
    - SHOP_MANAGER → CASHIER
    - SOCIAL_WORKER, None → UNKNOWN
    """

    role = serializers.SerializerMethodField()

    class Meta(AuthKitUserSerializer.Meta):
        model = CustomUser
        fields = AuthKitUserSerializer.Meta.fields + ("role",)

    def get_role(self, obj) -> str:
        """
        Map internal user roles to frontend-compatible roles.

        Returns:
            str: Mapped role value (CLIENT, RECIPIENT, CASHIER, or UNKNOWN)
        """
        match obj.role:
            case UserRole.CLIENT.value:
                return UserRole.CLIENT.value
            case UserRole.RECIPIENT.value:
                return UserRole.RECIPIENT.value
            case UserRole.CASHIER.value | UserRole.SHOP_MANAGER.value:
                return UserRole.CASHIER.value
            case _:
                return "UNKNOWN"


class CustomRegisterSerializer(AuthKitRegisterSerializer):
    """
    Custom registration serializer that automatically creates a Client role
    for newly registered users via the API registration endpoint.
    Users created via admin or other methods will NOT have a Client created automatically.
    """

    def custom_signup(self, request, user):
        """Override custom_signup to create Client role after user creation."""
        Client.objects.create(user=user)


class AddressLocationSerializerMixin:
    """
    Mixin for serializers that need to handle address and location fields.
    Provides common methods for constructing full addresses and extracting coordinates.
    """

    def get_full_address(self, obj):
        """Construct full address from structured fields."""
        parts = []
        if obj.street_number:
            parts.append(obj.street_number)
        if obj.street_name:
            parts.append(obj.street_name)
        address_line = " ".join(parts) if parts else ""

        if obj.postal_code and obj.city:
            if address_line:
                return f"{address_line}, {obj.postal_code} {obj.city}"
            return f"{obj.postal_code} {obj.city}"
        elif address_line:
            return address_line
        return ""

    def get_latitude(self, obj):
        """Extract latitude from location Point."""
        return obj.latitude

    def get_longitude(self, obj):
        """Extract longitude from location Point."""
        return obj.longitude


class SocialCenterSerializer(AddressLocationSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for SocialCenter model with full address constructed from structured fields.
    """

    full_address = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = SocialCenter
        fields = [
            "id",
            "name",
            "mail",
            "full_address",
            "street_number",
            "street_name",
            "postal_code",
            "city",
            "latitude",
            "longitude",
        ]
        read_only_fields = ["id"]


class ShopSerializer(AddressLocationSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for Shop model with full address constructed from structured fields.
    """

    full_address = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = [
            "id",
            "name",
            "full_address",
            "street_number",
            "street_name",
            "postal_code",
            "city",
            "latitude",
            "longitude",
            "social_center",
        ]
        read_only_fields = ["id"]


class ArticleInputSerializer(serializers.Serializer):
    """
    Serializer for individual article input with barcode.
    Used as part of bulk article creation.
    """

    barcode = serializers.IntegerField(min_value=0, help_text="EAN-13 or similar product barcode (numeric only)")
    name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    img_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    thumb_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    brand_label = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ArticleSerializer(serializers.ModelSerializer):
    """
    Serializer for Article model output.
    """

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

    def get_shop(self, obj):
        """Return shop information."""
        return {
            "id": obj.shop.id,
            "name": obj.shop.name,
        }

    def get_cart(self, obj):
        """Return cart information if article is assigned to a cart."""
        if obj.cart:
            return {
                "id": obj.cart.id,
                "status": obj.cart.status,
            }
        return None

    def get_status(self, obj):
        """
        Calculate article status based on cart assignment.
        - AVAILABLE: No cart assigned
        - ASSIGNED or COLLECTED: Based on cart status
        """
        if not obj.cart:
            return "AVAILABLE"
        return obj.cart.status


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
                name=article_data.get("name", ""),  # Name from request or empty for later enrichment
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


class CartSerializer(serializers.ModelSerializer):
    """
    Serializer for Cart model output.
    """

    shop_name = serializers.CharField(source="shop.name", read_only=True)
    recipient_email = serializers.EmailField(source="recipient.user.email", read_only=True)
    recipient_name = serializers.SerializerMethodField()
    articles = ArticleCartSerializer(many=True, read_only=True)

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
            "articles",
        ]
        read_only_fields = ["id", "collected_at"]

    def get_recipient_name(self, obj):
        """Return the full name of the recipient."""
        if obj.recipient is None:
            return None
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

        if request is None:
            raise serializers.ValidationError("Request context is required.")
        if not cart:
            raise serializers.ValidationError("Cart context is required.")
        if not recipient:
            raise serializers.ValidationError("Recipient context is required.")

        if cart.status != CartStatus.ASSIGNED.value:
            raise serializers.ValidationError(
                {"status": (f"Cart must be in ASSIGNED status to be collected. Current status: {cart.status}")}
            )
        cashier = getattr(request.user, "cashier", None)
        if not cashier or cashier.shop != cart.shop:
            raise serializers.ValidationError({"shop": "You can only collect carts from your shop."})

        if cart.recipient != recipient:
            raise serializers.ValidationError({"recipient": "The cart does not belong to this recipient."})

        return attrs

    def update(self, instance, validated_data):
        """Update the cart collected_at timestamp (status is computed automatically)."""
        instance.collected_at = timezone.now()
        instance.save()
        return instance

from django.utils import timezone
from rest_framework import serializers

from api.articles.serializers import ArticleCartSerializer
from api.enums import CartStatus
from api.models import Cart


class CartSerializer(serializers.ModelSerializer):
    """Serializer for Cart model output."""

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

    def get_recipient_name(self, obj) -> str | None:
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
        """Update the cart collected_at timestamp (status is computed
        automatically)."""
        instance.collected_at = timezone.now()
        instance.save()
        return instance

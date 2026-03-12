from rest_framework import serializers

from api.models import Shop


class AddressLocationSerializerMixin:
    """
    Mixin for serializers that need to handle address and location fields.
    Provides common methods for constructing full addresses and extracting
    coordinates.
    """

    def get_full_address(self, obj) -> str:
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

    def get_latitude(self, obj) -> float | None:
        """Extract latitude from location Point."""
        return obj.latitude

    def get_longitude(self, obj) -> float | None:
        """Extract longitude from location Point."""
        return obj.longitude


class ShopSerializer(
    AddressLocationSerializerMixin,
    serializers.ModelSerializer,
):
    """
    Serializer for Shop model with full address constructed from structured
    fields.
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

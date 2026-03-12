from rest_framework import serializers

from api.models import SocialCenter
from api.shops.serializers import AddressLocationSerializerMixin


class SocialCenterSerializer(
    AddressLocationSerializerMixin,
    serializers.ModelSerializer,
):
    """
    Serializer for SocialCenter model with full address constructed from
    structured fields.
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

from auth_kit.serializers.user import UserSerializer as AuthKitUserSerializer
from rest_framework import serializers

from .models import CustomUser


class CustomUserSerializer(AuthKitUserSerializer):
    """
    Custom serializer for CustomUser that extends auth_kit's UserSerializer.
    Adds the 'role' field dynamically calculated from OneToOne relationships.
    """

    role = serializers.ReadOnlyField()

    class Meta(AuthKitUserSerializer.Meta):
        model = CustomUser
        fields = AuthKitUserSerializer.Meta.fields + ("role",)

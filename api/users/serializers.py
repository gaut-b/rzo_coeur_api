from auth_kit.serializers.registration import RegisterSerializer as AuthKitRegisterSerializer
from auth_kit.serializers.user import UserSerializer as AuthKitUserSerializer
from rest_framework import serializers

from api.enums import UserRole
from api.models import Client, CustomUser


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
    Users created via admin or other methods will NOT have a Client created
    automatically.
    """

    def custom_signup(self, request, user):
        """Override custom_signup to create Client role after user creation."""
        Client.objects.create(user=user)

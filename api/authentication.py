"""
Custom authentication classes for the API.
"""

from auth_kit.authentication import JWTCookieAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken
from rest_framework_simplejwt.settings import api_settings

from .models import CustomUser


class SelectRelatedJWTAuthentication(JWTCookieAuthentication):
    """
    JWT authentication that pre-fetches all role-related profiles in a single
    query, preventing N+1 queries when accessing ``request.user.role``.
    """

    def get_user(self, validated_token):
        """
        Retrieve the user and eagerly load all role-related OneToOne profiles
        (client, socialworker, recipient, cashier) via a single JOIN query.
        """
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError as exc:
            raise InvalidToken("Token contained no recognizable user identification") from exc

        try:
            user = CustomUser.objects.select_related(
                "client",
                "socialworker",
                "recipient",
                "cashier",
            ).get(**{api_settings.USER_ID_FIELD: user_id})
        except CustomUser.DoesNotExist as exc:
            raise AuthenticationFailed("User not found", code="user_not_found") from exc

        if not user.is_active:
            raise AuthenticationFailed("User is inactive", code="user_inactive")

        return user

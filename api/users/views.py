"""
Custom user-profile view — extends auth_kit's UserView with account deletion.
"""

from typing import Any

import structlog
from auth_kit.jwt_auth import unset_jwt_cookies
from auth_kit.views import UserView as AuthKitUserView
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from api.enums import UserRole
from api.models import CustomUser

logger = structlog.get_logger(__name__)

# Only self-service roles may delete their own account via this endpoint;
# cashier/social-worker/admin accounts are managed by admins.
_SELF_DELETABLE_ROLES = {UserRole.CLIENT.value, UserRole.RECIPIENT.value}


def anonymize_user(user: CustomUser) -> None:
    """
    Scrub PII and deactivate *user* without deleting the row.

    Keeps the underlying Client/Recipient profile (and its Articles/Carts)
    intact — only the CustomUser row is anonymized — so CASCADE deletes
    never wipe shop/social-center history.
    """
    user.email = f"deleted-user-{user.pk}@deleted.invalid"
    user.first_name = ""
    user.last_name = ""
    user.set_unusable_password()
    user.is_active = False
    user.save(update_fields=["email", "first_name", "last_name", "password", "is_active"])


class CustomUserView(AuthKitUserView):
    """Adds account deletion (anonymize + deactivate) to auth_kit's UserView."""

    @extend_schema(
        summary="Delete own account",
        description="""
        Deletes the authenticated user's account.

        **Authentication**: Required (JWT Cookie)

        **Permission**: CLIENT or RECIPIENT role only

        Anonymizes the account (email, name, password) and deactivates it —
        the underlying profile and historical Articles/Carts are kept for
        shop/social-center reporting, but the user can no longer log in.
        Clears auth cookies on success.
        """,
        request=None,
        responses={204: None},
        tags=["Users"],
    )
    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Anonymize and deactivate the authenticated user's account."""
        user: CustomUser = request.user
        if user.role not in _SELF_DELETABLE_ROLES:
            return Response(
                {"detail": "Only CLIENT and RECIPIENT accounts can be deleted via this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        anonymize_user(user)
        logger.info("account_deleted", user_id=user.pk, role=user.role)

        response = Response(status=status.HTTP_204_NO_CONTENT)
        unset_jwt_cookies(response)
        return response

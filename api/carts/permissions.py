from rest_framework.permissions import BasePermission

from api.enums import UserRole


class IsRecipient(BasePermission):
    """
    Permission class that allows access only to users with the RECIPIENT role.
    """

    message = "RECIPIENT role required."

    def has_permission(self, request, view):
        """Check if the user is authenticated and has the RECIPIENT role."""
        return request.user.is_authenticated and request.user.role == UserRole.RECIPIENT.value

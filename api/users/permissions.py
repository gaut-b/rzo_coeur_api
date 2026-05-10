from rest_framework.permissions import BasePermission

from api.enums import UserRole


class IsClient(BasePermission):
    """
    Permission class that allows access only to users with the CLIENT role.
    """

    message = "CLIENT role required."

    def has_permission(self, request, view):
        """Check if the user is authenticated and has the CLIENT role."""
        return request.user.is_authenticated and request.user.role == UserRole.CLIENT.value

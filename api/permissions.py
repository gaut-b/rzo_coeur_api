from rest_framework.permissions import BasePermission

from .enums import UserRole


class IsCashier(BasePermission):
    """
    Permission class that allows access only to users with the CASHIER role.
    """

    def has_permission(self, request, view):
        """
        Check if the user is authenticated and has the CASHIER role.
        """
        return request.user.is_authenticated and request.user.role == UserRole.CASHIER

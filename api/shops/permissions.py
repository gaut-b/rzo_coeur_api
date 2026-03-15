from rest_framework.permissions import BasePermission

from api.enums import UserRole


class IsCashier(BasePermission):
    """
    Permission class that allows access only to users with the CASHIER role.
    """

    def has_permission(self, request, view):
        """Check if the user is authenticated and has the CASHIER role."""
        return request.user.is_authenticated and request.user.role == UserRole.CASHIER.value


class IsShopManager(BasePermission):
    """
    Permission class that allows access only to users with the SHOP_MANAGER
    role.
    """

    def has_permission(self, request, view):
        """Check if the user is authenticated and has the SHOP_MANAGER role."""
        return request.user.is_authenticated and request.user.role == UserRole.SHOP_MANAGER.value

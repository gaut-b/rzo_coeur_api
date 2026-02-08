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
        return request.user.is_authenticated and request.user.role == UserRole.CASHIER.value


class IsClient(BasePermission):
    """
    Permission class that allows access only to users with the CLIENT role.
    """

    def has_permission(self, request, view):
        """
        Check if the user is authenticated and has the CLIENT role.
        """

        return request.user.is_authenticated and request.user.role == UserRole.CLIENT.value


class IsRecipient(BasePermission):
    """
    Permission class that allows access only to users with the RECIPIENT role.
    """

    def has_permission(self, request, view):
        """
        Check if the user is authenticated and has the RECIPIENT role.
        """
        return request.user.is_authenticated and request.user.role == UserRole.RECIPIENT.value


class IsShopManager(BasePermission):
    """
    Permission class that allows access only to users with the SHOP_MANAGER role.
    """

    def has_permission(self, request, view):
        """
        Check if the user is authenticated and has the SHOP_MANAGER role.
        """
        return request.user.is_authenticated and request.user.role == UserRole.SHOP_MANAGER.value

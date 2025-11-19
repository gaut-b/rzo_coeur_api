from rest_framework import permissions

from .enums import UserRole


class IsCashier(permissions.BasePermission):
    """
    Permission class that allows access only to users with the CASHIER role.
    """

    def has_permission(self, request, view):
        """
        Check if the user is authenticated and has the CASHIER role.
        """
        return request.user.is_authenticated and request.user.role == UserRole.CASHIER.value


class IsClient(permissions.BasePermission):
    """
    Permission class that allows access only to users with the CLIENT role.
    """

    def has_permission(self, request, view):
        """
        Check if the user is authenticated and has the CLIENT role.
        """

        return request.user.is_authenticated and request.user.role == UserRole.CLIENT.value


class IsRecipient(permissions.BasePermission):
    """
    Permission class that allows access only to users with the RECIPIENT role.
    """

    def has_permission(self, request, view):
        """
        Check if the user is authenticated and has the RECIPIENT role.
        """
        return request.user.is_authenticated and request.user.role == UserRole.RECIPIENT.value


class IsSocialWorker(permissions.BasePermission):
    """
    Permission class that allows access only to users with the SOCIAL_WORKER role.
    """

    def has_permission(self, request, view):
        """
        Check if the user is authenticated and has the SOCIAL_WORKER role.
        """
        return request.user.role == UserRole.SOCIAL_WORKER.value and request.user.is_authenticated


class IsShopAdmin(permissions.BasePermission):
    """
    Permission class that allows access only to users with the SHOPADMIN role.
    """

    def has_permission(self, request, view):
        """
        Check if the user is authenticated and has the SHOPADMIN role.
        """
        return request.user.role == UserRole.SHOPADMIN.value and request.user.is_authenticated


class IsSocialCenterAdmin(permissions.BasePermission):
    """
    Permission class that allows access only to users with the SOCIALCENTERADMIN role.
    """

    def has_permission(self, request, view):
        is_social_admin = request.user.role == UserRole.SOCIALCENTERADMIN.value
        return is_social_admin and request.user.is_authenticated


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission class that allows access only to users with the database admin role.
    """

    def has_object_permission(self, request, view, obj):
        # Early return for GET, HEAD or OPTION requests
        if request.method in permissions.SAFE_METHODS:
            return True

        return obj.owner == request.user

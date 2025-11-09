from enum import Enum


class UserRole(str, Enum):
    """Enumeration of user roles in the system."""

    CLIENT = "CLIENT"
    SOCIAL_WORKER = "SOCIAL_WORKER"
    RECIPIENT = "RECIPIENT"
    CASHIER = "CASHIER"

    def __str__(self):
        return self.value

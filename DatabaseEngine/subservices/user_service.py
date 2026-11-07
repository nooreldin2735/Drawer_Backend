"""
User and session identification service.
Distinguishes authenticated users from guests.
"""

from typing import Any, Optional, Tuple
from django.contrib.auth.models import User


class UserService:
    """Resolves identity for WebSocket connections and REST requests."""

    @staticmethod
    def resolve_user_identity(
        user: Optional[Any] = None,
        raw_name: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Tuple[Optional[User], str, bool]:
        """
        Determines user entity, display name, and authentication status.
        Returns (User instance or None, display_name, is_authenticated).
        """
        if user and hasattr(user, "is_authenticated") and user.is_authenticated:
            # Authenticated user
            display_name = user.username or (user.get_full_name() if hasattr(user, "get_full_name") else "User")
            return user, display_name, True

        # Unauthenticated / guest session
        fallback_name = raw_name if raw_name and raw_name.strip() else "Guest"
        return None, fallback_name, False


user_service = UserService()


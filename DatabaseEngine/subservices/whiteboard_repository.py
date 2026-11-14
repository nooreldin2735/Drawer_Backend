"""
Whiteboard repository subservice.
Encapsulates all Django ORM operations for Whiteboard and WhiteboardVersion models.
"""

import logging
from typing import Any, Dict, List, Optional
from django.utils import timezone
from django.contrib.auth.models import User
from Dashboard.models import Whiteboard, WhiteboardVersion

logger = logging.getLogger(__name__)


class WhiteboardRepository:
    """Handles CRUD, snapshot saves, version checkpoints, and rollbacks."""

    @staticmethod
    def get_or_create(
        board_id: str,
        title: Optional[str] = None,
        user: Optional[User] = None,
        guest_name: str = "Guest",
    ) -> tuple[Whiteboard, bool]:
        """Fetches an existing whiteboard or creates a new one."""
        whiteboard, created = Whiteboard.objects.get_or_create(
            id=board_id,
            defaults={
                "title": title or f"Whiteboard {board_id[:8]}",
                "owner": user,
                "guest_name": guest_name,
                "snapshot": {"shapes": [], "version": 0},
                "version": 0,
            },
        )
        if not whiteboard.invite_code:
            whiteboard.save()
        if not created and user and not whiteboard.owner:
            # Associate anonymous board with user if user logs in
            whiteboard.owner = user
            whiteboard.save(update_fields=["owner"])
        return whiteboard, created

    @staticmethod
    def get_whiteboard(board_id: str) -> Optional[Whiteboard]:
        """Retrieves a whiteboard by its board ID."""
        try:
            wb = Whiteboard.objects.select_related("owner").get(id=board_id)
            if not wb.invite_code:
                wb.save()
            return wb
        except Whiteboard.DoesNotExist:
            return None

    @staticmethod
    def get_by_invite_code(invite_code: str) -> Optional[Whiteboard]:
        """Retrieves an active whiteboard by its invite code."""
        if not invite_code:
            return None
        code = invite_code.strip().upper()
        return Whiteboard.objects.select_related("owner").filter(invite_code__iexact=code, is_active=True).first()

    @staticmethod
    def verify_access(
        board_id: str,
        invite_code: Optional[str] = None,
        user: Optional[User] = None,
    ) -> tuple[bool, Optional[Whiteboard], str]:
        """
        Validates if user or guest can access a session:
        - Authenticated owner can access their own session.
        - Any participant can access with matching invite code.
        Returns: (is_allowed, whiteboard, reason)
        """
        try:
            wb = Whiteboard.objects.select_related("owner").get(id=board_id)
        except Whiteboard.DoesNotExist:
            return False, None, "Whiteboard session not found"

        if not wb.invite_code:
            wb.save()

        # Check owner access
        if user and getattr(user, "is_authenticated", False) and wb.owner_id == user.id:
            return True, wb, "Owner access"

        # Check invite code access
        if invite_code and wb.invite_code and wb.invite_code.upper() == invite_code.strip().upper():
            return True, wb, "Invite code verified"

        return False, wb, "Invalid or missing invite code"

    @staticmethod
    def save_session_closure(
        board_id: str,
        snapshot: Dict[str, Any],
        version: int,
        user: Optional[User] = None,
        saved_by_name: str = "Guest",
        note: str = "Session closed checkpoint",
    ) -> Optional[Whiteboard]:
        """
        Saves the durable state when a session closes:
        - Updates Whiteboard.snapshot with the latest drawing changes
        - Updates Whiteboard.version
        - Sets Whiteboard.last_closed_at
        - Automatically creates a new WhiteboardVersion historical entry
        """
        try:
            whiteboard, _ = Whiteboard.objects.get_or_create(
                id=board_id,
                defaults={
                    "title": f"Whiteboard {board_id[:8]}",
                    "owner": user,
                    "guest_name": saved_by_name,
                },
            )

            # Update board state
            whiteboard.snapshot = snapshot
            whiteboard.version = version
            whiteboard.last_closed_at = timezone.now()
            if user and not whiteboard.owner:
                whiteboard.owner = user
            whiteboard.save()

            # Record version snapshot if shapes exist or version incremented
            shapes = snapshot.get("shapes", [])
            # Only create version entry if version is not already recorded
            if not WhiteboardVersion.objects.filter(whiteboard=whiteboard, version_number=version).exists():
                WhiteboardVersion.objects.create(
                    whiteboard=whiteboard,
                    version_number=version,
                    snapshot=snapshot,
                    saved_by=saved_by_name,
                    note=note,
                )
                logger.info("Created WhiteboardVersion %d for board %s (%d shapes)", version, board_id, len(shapes))

            return whiteboard
        except Exception as exc:
            logger.error("Failed to save whiteboard session closure for %s: %s", board_id, exc)
            return None

    @staticmethod
    def list_whiteboards(user: Optional[User] = None, guest_name: Optional[str] = None) -> List[Whiteboard]:
        """
        Lists whiteboards:
        - If user is authenticated: boards owned by user + active guest boards
        - If guest: all active guest boards or public boards
        """
        qs = Whiteboard.objects.filter(is_active=True)
        if user and user.is_authenticated:
            # User's whiteboards first
            return list(qs.filter(owner=user))
        elif guest_name and guest_name != "Guest":
            return list(qs.filter(guest_name=guest_name))
        return list(qs)

    @staticmethod
    def delete_whiteboard(board_id: str, user: Optional[User] = None) -> bool:
        """Deletes a whiteboard and its version history."""
        try:
            wb = Whiteboard.objects.get(id=board_id)
            if user and user.is_authenticated and wb.owner and wb.owner != user:
                return False  # Permission denied
            wb.delete()
            return True
        except Whiteboard.DoesNotExist:
            return False

    @staticmethod
    def list_versions(board_id: str) -> List[WhiteboardVersion]:
        """Retrieves all version checkpoints for a whiteboard."""
        return list(WhiteboardVersion.objects.filter(whiteboard_id=board_id).order_by("-version_number"))

    @staticmethod
    def restore_version(board_id: str, version_number: int) -> Optional[Whiteboard]:
        """
        Restores a whiteboard to a previous version checkpoint.
        Updates the main snapshot to match that version.
        """
        try:
            version_obj = WhiteboardVersion.objects.get(
                whiteboard_id=board_id,
                version_number=version_number,
            )
            whiteboard = version_obj.whiteboard
            # Restore snapshot from version
            whiteboard.snapshot = version_obj.snapshot
            whiteboard.version = whiteboard.version + 1  # Increment version to notify peers of rollback
            whiteboard.save(update_fields=["snapshot", "version", "updated_at"])

            # Create a rollback checkpoint entry
            WhiteboardVersion.objects.create(
                whiteboard=whiteboard,
                version_number=whiteboard.version,
                snapshot=version_obj.snapshot,
                saved_by=f"Restored from v{version_number}",
                note=f"Rollback to version {version_number}",
            )
            return whiteboard
        except WhiteboardVersion.DoesNotExist:
            return None


whiteboard_repository = WhiteboardRepository()


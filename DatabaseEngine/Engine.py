"""
Database Engine Facade.
Centralizes all PostgreSQL database operations for Whiteboard collaboration,
session saving upon closure, user identity resolution, and dashboard queries.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User

from .subservices import (
    UserService,
    user_service,
    SessionManager,
    session_manager,
    WhiteboardRepository,
    whiteboard_repository,
)

logger = logging.getLogger(__name__)


class DatabaseEngine:
    """
    Primary interface for persistent storage operations.
    Consumers and REST views interact exclusively through this engine.
    """

    def __init__(
        self,
        repo: WhiteboardRepository = whiteboard_repository,
        sessions: SessionManager = session_manager,
        users: UserService = user_service,
    ) -> None:
        self.repo = repo
        self.sessions = sessions
        self.users = users

    # =========================================================================
    # Async Methods (used by WebSocket consumers and async services)
    # =========================================================================

    async def save_session_closure(
        self,
        board_id: str,
        snapshot: Dict[str, Any],
        version: int,
        user: Optional[User] = None,
        saved_by_name: str = "Guest",
        note: str = "Session closed save",
    ) -> Optional[Any]:
        """
        Persists the durable whiteboard state when a session closes:
        - Saves latest shape data JSON into PostgreSQL
        - Bumps version and records a version checkpoint
        """
        return await sync_to_async(self.repo.save_session_closure)(
            board_id=board_id,
            snapshot=snapshot,
            version=version,
            user=user,
            saved_by_name=saved_by_name,
            note=note,
        )

    async def load_initial_snapshot(self, board_id: str) -> Optional[Dict[str, Any]]:
        """
        Loads the saved whiteboard snapshot from PostgreSQL if it exists.
        Allows resuming previous drawings when connecting to a board session.
        """
        wb = await sync_to_async(self.repo.get_whiteboard)(board_id)
        if wb and wb.snapshot and isinstance(wb.snapshot, dict) and wb.snapshot.get("shapes"):
            return {
                "shapes": wb.snapshot.get("shapes", []),
                "version": wb.version,
                "type": "snapshot",
            }
        return None

    async def register_session_participant(
        self,
        board_id: str,
        channel_name: str,
        user: Optional[User] = None,
        display_name: str = "Guest",
    ) -> int:
        """Registers a newly connected client channel in the session manager."""
        return self.sessions.register_connection(
            board_id=board_id,
            channel_name=channel_name,
            user=user,
            display_name=display_name,
        )

    async def unregister_session_participant(
        self,
        channel_name: str,
    ) -> tuple[Optional[str], bool, int]:
        """
        Unregisters a disconnecting client.
        Returns: (board_id, is_room_now_empty, remaining_count)
        """
        return self.sessions.unregister_connection(channel_name)

    async def get_whiteboard_details_async(self, board_id: str) -> Optional[Dict[str, Any]]:
        """Async version of get_whiteboard_details."""
        return await sync_to_async(self.get_whiteboard_details)(board_id)

    async def get_versions_async(self, board_id: str) -> List[Dict[str, Any]]:
        """Async version of get_versions."""
        return await sync_to_async(self.get_versions)(board_id)

    async def restore_version_async(self, board_id: str, version_number: int) -> Optional[Dict[str, Any]]:
        """Async version of restore_version."""
        return await sync_to_async(self.restore_version)(board_id, version_number)

    async def get_user_whiteboards_async(
        self,
        user: Optional[User] = None,
        guest_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Async version of get_user_whiteboards."""
        return await sync_to_async(self.get_user_whiteboards)(user, guest_name)

    # =========================================================================
    # Synchronous Methods (used by Dashboard REST views and tests)
    # =========================================================================

    def get_user_whiteboards(
        self,
        user: Optional[User] = None,
        guest_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Returns serialized whiteboards for dashboard presentation."""
        boards = self.repo.list_whiteboards(user=user, guest_name=guest_name)
        return [b.to_dict() for b in boards]

    def create_whiteboard(
        self,
        title: str,
        board_id: Optional[str] = None,
        user: Optional[User] = None,
        guest_name: str = "Guest",
    ) -> Dict[str, Any]:
        """Creates a new whiteboard record."""
        import uuid
        effective_id = board_id or str(uuid.uuid4())[:8]
        wb, _ = self.repo.get_or_create(
            board_id=effective_id,
            title=title,
            user=user,
            guest_name=guest_name,
        )
        return wb.to_dict()

    def get_whiteboard_details(self, board_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves details of a single whiteboard."""
        wb = self.repo.get_whiteboard(board_id)
        return wb.to_dict() if wb else None

    def delete_whiteboard(self, board_id: str, user: Optional[User] = None) -> bool:
        """Deletes a whiteboard and its versions."""
        return self.repo.delete_whiteboard(board_id, user=user)

    def get_versions(self, board_id: str) -> List[Dict[str, Any]]:
        """Retrieves version history for a whiteboard."""
        versions = self.repo.list_versions(board_id)
        return [v.to_dict() for v in versions]

    def restore_version(self, board_id: str, version_number: int) -> Optional[Dict[str, Any]]:
        """Rolls back a whiteboard to a previous version."""
        wb = self.repo.restore_version(board_id, version_number)
        return wb.to_dict() if wb else None


# Shared singleton instance
db_engine = DatabaseEngine()

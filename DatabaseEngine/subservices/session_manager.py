"""
Session manager subservice.
Manages active WebSocket sessions per board and detects session closure.
"""

import logging
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


class SessionManager:
    """
    In-memory tracking of active channel connections per whiteboard room.
    Allows detecting when all participants have left a whiteboard session so
    the session closure persistence can be safely triggered.
    """

    def __init__(self) -> None:
        # board_id -> set of channel_names
        self._active_connections: Dict[str, Set[str]] = {}
        # channel_name -> { "board_id": str, "user": Any, "name": str }
        self._channel_metadata: Dict[str, Dict[str, Any]] = {}

    def register_connection(
        self,
        board_id: str,
        channel_name: str,
        user: Optional[Any] = None,
        display_name: str = "Guest",
    ) -> int:
        """Registers a channel connection to a whiteboard room."""
        if board_id not in self._active_connections:
            self._active_connections[board_id] = set()

        self._active_connections[board_id].add(channel_name)
        self._channel_metadata[channel_name] = {
            "board_id": board_id,
            "user": user,
            "name": display_name,
        }
        count = len(self._active_connections[board_id])
        logger.debug("Board %s: participant %s joined (total: %d)", board_id, channel_name, count)
        return count

    def unregister_connection(self, channel_name: str) -> tuple[Optional[str], bool, int]:
        """
        Unregisters a channel connection.
        Returns:
            (board_id, is_room_now_empty, remaining_count)
        """
        meta = self._channel_metadata.pop(channel_name, None)
        if not meta:
            return None, False, 0

        board_id = meta["board_id"]
        if board_id in self._active_connections:
            self._active_connections[board_id].discard(channel_name)
            remaining = len(self._active_connections[board_id])
            if remaining == 0:
                self._active_connections.pop(board_id, None)
                logger.info("Board %s: all participants disconnected. Session closed.", board_id)
                return board_id, True, 0
            return board_id, False, remaining

        return board_id, True, 0

    def get_room_count(self, board_id: str) -> int:
        """Returns the number of active participants in a board."""
        return len(self._active_connections.get(board_id, set()))

    def is_room_active(self, board_id: str) -> bool:
        """Checks if a room has any active connected participants."""
        return self.get_room_count(board_id) > 0


session_manager = SessionManager()


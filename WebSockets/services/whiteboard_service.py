"""
Whiteboard business logic service.
Orchestrates room resolution, message parsing, shape lifecycle dispatching,
and broadcast envelope preparation so consumers act purely as transport interfaces.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional, Tuple, Union
from urllib.parse import parse_qs

from DatabaseEngine import db_engine
from .shape_service import ShapeService, shape_service
from .types import (
    CursorMoveOperation,
    OperationType,
    ShapeAddOperation,
    ShapeRemoveOperation,
    ShapeUpdateOperation,
    SnapshotMessage,
    WhiteboardMessage,
    parse_operation,
)

logger = logging.getLogger(__name__)


@dataclass
class ProcessOperationRequest:
    """Encapsulates the input parameters for processing an incoming WebSocket operation."""
    board_id: str
    raw_data: Union[str, dict[str, Any]]
    sender_channel_name: str = ""


# Alias for concise reference
OperationRequest = ProcessOperationRequest


@dataclass
class ProcessResult:
    """Encapsulates the output of processing a WebSocket message."""
    broadcast_data: Optional[dict[str, Any]] = None
    direct_response: Optional[dict[str, Any]] = None
    op_type: Optional[str] = None
    error: Optional[str] = None


class WhiteboardService:
    """
    Core domain service orchestrating whiteboard interactions.
    Consumers interface exclusively with this service.
    """

    def __init__(self, shapes: ShapeService = shape_service) -> None:
        self.shape_service = shapes

    def extract_room_info(self, scope: dict[str, Any]) -> Tuple[str, str]:
        """
        Extracts boardId and userId from the connection scope.
        Supports query params (?boardId=...&userId=...) or URL route kwargs.
        """
        query_string = scope.get("query_string", b"").decode("utf-8")
        parsed_query = parse_qs(query_string)

        # 1. Check URL kwargs (e.g. /ws/canvas/<room_name>/)
        url_kwargs = scope.get("url_route", {}).get("kwargs", {})
        room_name = url_kwargs.get("room_name")

        # 2. Check query param ?boardId=...
        if not room_name and "boardId" in parsed_query:
            room_name = parsed_query["boardId"][0]

        # 3. Default fallback
        if not room_name:
            room_name = "default-board"

        # Extract user ID if provided
        user_id = parsed_query.get("userId", [""])[0]

        return room_name, user_id

    def extract_user_identity(self, scope: dict[str, Any]) -> Tuple[str, bool]:
        """
        Extracts user identity from session scope:
        If authenticated, returns (username, True).
        If not authenticated, returns ('Guest', False).
        """
        user = scope.get("user")
        if user and getattr(user, "is_authenticated", False):
            return user.username, True

        query_string = scope.get("query_string", b"").decode("utf-8")
        parsed_query = parse_qs(query_string)
        guest_param = parsed_query.get("userName", ["Guest"])[0]
        return guest_param or "Guest", False

    def get_group_name(self, board_id: str) -> str:
        """Returns the Channel Layer group name for a given board."""
        # Sanitize characters for Django channel layer group names
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in board_id)
        return f"board_{safe_id}"

    async def get_initial_snapshot(self, board_id: str) -> SnapshotMessage:
        """
        Retrieves the initial snapshot of all shapes for the newly joined client.
        Loads from DatabaseEngine if not yet in memory.
        """
        if not await self.shape_service.has_shapes(board_id):
            persistent_snapshot = await db_engine.load_initial_snapshot(board_id)
            if persistent_snapshot:
                await self.shape_service.load_snapshot(
                    board_id=board_id,
                    shapes_data=persistent_snapshot.get("shapes", []),
                    version=persistent_snapshot.get("version", 0),
                )

        return await self.shape_service.get_snapshot(board_id)

    async def save_session_closure(
        self,
        board_id: str,
        user: Optional[Any] = None,
        saved_by_name: str = "Guest",
    ) -> None:
        """
        Persists the durable whiteboard state (shapes, version) to PostgreSQL via DatabaseEngine
        when the session closes.
        """
        snapshot = await self.shape_service.get_snapshot(board_id)
        snapshot_dict = snapshot.to_dict()
        await db_engine.save_session_closure(
            board_id=board_id,
            snapshot=snapshot_dict,
            version=snapshot.version,
            user=user if user and getattr(user, "is_authenticated", False) else None,
            saved_by_name=saved_by_name,
            note="Session closed checkpoint",
        )

    async def process_operation(
        self,
        request: Optional[ProcessOperationRequest] = None,
        *,
        board_id: Optional[str] = None,
        raw_data: Optional[Union[str, dict[str, Any]]] = None,
        sender_channel_name: Optional[str] = None,
    ) -> ProcessResult:
        """
        Processes an incoming message from a WebSocket client:
        - Accepts either a ProcessOperationRequest dataclass or individual arguments.
        - Validates and parses the envelope
        - Mutates persistent shape state via ShapeService
        - Prepares broadcast payloads for room participants
        """
        if request is not None:
            active_board_id = request.board_id
            active_raw_data = request.raw_data
            active_sender_channel_name = request.sender_channel_name
        else:
            if board_id is None or raw_data is None:
                return ProcessResult(error="Missing required operation parameters")
            active_board_id = board_id
            active_raw_data = raw_data
            active_sender_channel_name = sender_channel_name or ""

        try:
            op: WhiteboardMessage = parse_operation(active_raw_data)
        except Exception as exc:
            logger.warning("Failed to parse incoming whiteboard operation: %s", exc)
            return ProcessResult(error=str(exc))

        # 1. Add Shape
        if isinstance(op, ShapeAddOperation):
            await self.shape_service.add_shape(
                board_id=active_board_id,
                shape=op.payload.shape,
                version=op.version,
            )
            return ProcessResult(
                broadcast_data=op.to_dict(),
                op_type=OperationType.SHAPE_ADD.value,
            )

        # 2. Update Shape
        elif isinstance(op, ShapeUpdateOperation):
            updated_shape = await self.shape_service.update_shape(
                board_id=active_board_id,
                shape_id=op.payload.id,
                changes=op.payload.changes,
                version=op.version,
            )
            if updated_shape is None:
                logger.debug("Shape %s not found on board %s to update", op.payload.id, active_board_id)

            return ProcessResult(
                broadcast_data=op.to_dict(),
                op_type=OperationType.SHAPE_UPDATE.value,
            )

        # 3. Remove Shape
        elif isinstance(op, ShapeRemoveOperation):
            await self.shape_service.remove_shape(
                board_id=active_board_id,
                shape_id=op.payload.id,
                version=op.version,
            )
            return ProcessResult(
                broadcast_data=op.to_dict(),
                op_type=OperationType.SHAPE_REMOVE.value,
            )

        # 4. Ephemeral Cursor Movement (never persisted to DB/disk)
        elif isinstance(op, CursorMoveOperation):
            return ProcessResult(
                broadcast_data=op.to_dict(),
                op_type=OperationType.CURSOR_MOVE.value,
            )

        # 5. Snapshot request (if requested explicitly)
        elif isinstance(op, SnapshotMessage):
            snapshot = await self.shape_service.get_snapshot(active_board_id)
            return ProcessResult(
                direct_response=snapshot.to_dict(),
                op_type=OperationType.SNAPSHOT.value,
            )

        return ProcessResult(error=f"Unhandled operation type: {getattr(op, 'type', 'unknown')}")


# Shared singleton instance
whiteboard_service = WhiteboardService()

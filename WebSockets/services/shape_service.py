"""
Shape service for whiteboard real-time collaboration.
Encapsulates all shape CRUD operations, state manipulation, and snapshot generation.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from .types import (
    Point,
    Shape,
    ShapeStyle,
    SnapshotMessage,
)


class ShapeService:
    """
    Manages in-memory durable shapes and version counters for whiteboard rooms.
    Thread-safe and async-compatible.
    """

    def __init__(self) -> None:
        # Map: board_id -> (shape_id -> Shape)
        self._board_shapes: dict[str, dict[str, Shape]] = {}
        # Map: board_id -> int
        self._board_versions: dict[str, int] = {}
        self._lock = asyncio.Lock()

    def _ensure_board(self, board_id: str) -> None:
        if board_id not in self._board_shapes:
            self._board_shapes[board_id] = {}
            self._board_versions[board_id] = 0

    async def get_shapes(self, board_id: str) -> list[Shape]:
        """Returns all shapes currently on the specified board."""
        async with self._lock:
            self._ensure_board(board_id)
            return list(self._board_shapes[board_id].values())

    async def get_shape(self, board_id: str, shape_id: str) -> Optional[Shape]:
        """Retrieves a single shape by its ID."""
        async with self._lock:
            self._ensure_board(board_id)
            return self._board_shapes[board_id].get(shape_id)

    async def get_version(self, board_id: str) -> int:
        """Returns the current monotonic version counter for the board."""
        async with self._lock:
            self._ensure_board(board_id)
            return self._board_versions[board_id]

    async def add_shape(self, board_id: str, shape: Shape, version: Optional[int] = None) -> Shape:
        """
        Adds a new shape to the board snapshot and increments the version counter.
        """
        async with self._lock:
            self._ensure_board(board_id)
            self._board_shapes[board_id][shape.id] = shape
            if version is not None and version > self._board_versions[board_id]:
                self._board_versions[board_id] = version
            else:
                self._board_versions[board_id] += 1
            return shape

    async def update_shape(
        self,
        board_id: str,
        shape_id: str,
        changes: dict[str, Any],
        version: Optional[int] = None,
    ) -> Optional[Shape]:
        """
        Applies partial updates (translation, resize, restyling, data) to an existing shape.
        """
        async with self._lock:
            self._ensure_board(board_id)
            shape = self._board_shapes[board_id].get(shape_id)
            if not shape:
                return None

            # Apply geometry changes
            if "x" in changes:
                shape.x = float(changes["x"])
            if "y" in changes:
                shape.y = float(changes["y"])
            if "width" in changes:
                shape.width = float(changes["width"])
            if "height" in changes:
                shape.height = float(changes["height"])
            if "type" in changes:
                shape.type = str(changes["type"])

            # Apply styling changes
            if "style" in changes and isinstance(changes["style"], dict):
                style_dict = changes["style"]
                if "strokeColor" in style_dict:
                    shape.style.strokeColor = style_dict["strokeColor"]
                if "fillColor" in style_dict:
                    shape.style.fillColor = style_dict["fillColor"]
                if "strokeWidth" in style_dict:
                    shape.style.strokeWidth = float(style_dict["strokeWidth"])
                if "opacity" in style_dict:
                    shape.style.opacity = float(style_dict["opacity"])

            # Apply custom metadata or freehand points
            if "data" in changes and isinstance(changes["data"], dict):
                shape.data = {**shape.data, **changes["data"]}

            if version is not None and version > self._board_versions[board_id]:
                self._board_versions[board_id] = version
            else:
                self._board_versions[board_id] += 1

            return shape

    async def remove_shape(
        self,
        board_id: str,
        shape_id: str,
        version: Optional[int] = None,
    ) -> Optional[Shape]:
        """
        Removes a shape from the board by ID and increments version counter.
        """
        async with self._lock:
            self._ensure_board(board_id)
            removed = self._board_shapes[board_id].pop(shape_id, None)
            if removed is not None:
                if version is not None and version > self._board_versions[board_id]:
                    self._board_versions[board_id] = version
                else:
                    self._board_versions[board_id] += 1
            return removed

    async def get_snapshot(self, board_id: str) -> SnapshotMessage:
        """
        Generates the full initial snapshot message to deliver to connecting clients.
        """
        async with self._lock:
            self._ensure_board(board_id)
            shapes_list = list(self._board_shapes[board_id].values())
            version = self._board_versions[board_id]
            return SnapshotMessage(
                shapes=shapes_list,
                version=version,
            )

    async def clear_board(self, board_id: str) -> None:
        """Removes all shapes from a board."""
        async with self._lock:
            self._board_shapes[board_id] = {}
            self._board_versions[board_id] = 0


# Shared singleton instance across WebSocket connections
shape_service = ShapeService()

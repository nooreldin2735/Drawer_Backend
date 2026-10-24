"""
Data classes and types for the Whiteboard Collaboration Protocol.
Defines serializable schemas matching BACKEND_SPEC.md and Drawer frontend contracts.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Generic, Optional, TypeVar, Union


# ==============================================================================
# Enums
# ==============================================================================

class OperationType(str, Enum):
    """Supported operation discriminators."""
    SNAPSHOT = "snapshot"
    SHAPE_ADD = "shape:add"
    SHAPE_UPDATE = "shape:update"
    SHAPE_REMOVE = "shape:remove"
    CURSOR_MOVE = "cursor:move"


class ShapeType(str, Enum):
    """Standard shape types supported by the whiteboard."""
    # Basic shapes
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    LINE = "line"
    TRIANGLE = "triangle"
    FREEHAND = "freehand"

    # Premade shapes
    STAR = "star"
    ARROW = "arrow"
    HEXAGON = "hexagon"
    DIAMOND = "diamond"
    HEART = "heart"
    SPEECH_BUBBLE = "speech_bubble"


# ==============================================================================
# Geometry & Styling
# ==============================================================================

@dataclass
class Point:
    """2D point coordinate in screen or world space."""
    x: float
    y: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Point:
        return cls(x=float(data["x"]), y=float(data["y"]))

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y}


@dataclass
class ShapeStyle:
    """Styling attributes for vector shapes."""
    strokeColor: str = "#6366f1"
    fillColor: str = "transparent"
    strokeWidth: float = 2.0
    opacity: float = 1.0

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> ShapeStyle:
        if not data:
            return cls()
        return cls(
            strokeColor=data.get("strokeColor", "#6366f1"),
            fillColor=data.get("fillColor", "transparent"),
            strokeWidth=float(data.get("strokeWidth", 2.0)),
            opacity=float(data.get("opacity", 1.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "strokeColor": self.strokeColor,
            "fillColor": self.fillColor,
            "strokeWidth": self.strokeWidth,
            "opacity": self.opacity,
        }


# ==============================================================================
# Shape Entity
# ==============================================================================

@dataclass
class Shape:
    """
    Serializable whiteboard shape representation.
    For freehand shapes, data["points"] holds a list of Point dictionaries.
    """
    id: str
    type: str
    x: float
    y: float
    width: float
    height: float
    style: ShapeStyle = field(default_factory=ShapeStyle)
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Shape:
        return cls(
            id=data["id"],
            type=data["type"],
            x=float(data["x"]),
            y=float(data["y"]),
            width=float(data["width"]),
            height=float(data["height"]),
            style=ShapeStyle.from_dict(data.get("style")),
            data=data.get("data", {}) or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "style": self.style.to_dict(),
            "data": self.data,
        }


# ==============================================================================
# Operation Payloads
# ==============================================================================

@dataclass
class ShapeAddPayload:
    """Payload when a new shape is placed or drawn on the whiteboard."""
    shape: Shape

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShapeAddPayload:
        return cls(shape=Shape.from_dict(data["shape"]))

    def to_dict(self) -> dict[str, Any]:
        return {"shape": self.shape.to_dict()}


@dataclass
class ShapeUpdatePayload:
    """Payload when a shape is translated, resized, or restyled."""
    id: str
    changes: dict[str, Any]
    previous: Optional[dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShapeUpdatePayload:
        return cls(
            id=data["id"],
            changes=data.get("changes", {}),
            previous=data.get("previous"),
        )

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "id": self.id,
            "changes": self.changes,
        }
        if self.previous is not None:
            res["previous"] = self.previous
        return res


@dataclass
class ShapeRemovePayload:
    """Payload when one or more shapes are removed from the whiteboard."""
    id: str
    shape: Optional[Shape] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShapeRemovePayload:
        shape_data = data.get("shape")
        return cls(
            id=data["id"],
            shape=Shape.from_dict(shape_data) if shape_data else None,
        )

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {"id": self.id}
        if self.shape is not None:
            res["shape"] = self.shape.to_dict()
        return res


@dataclass
class CursorMovePayload:
    """Payload for broadcasting throttled cursor positions."""
    x: float
    y: float
    userName: Optional[str] = None
    color: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CursorMovePayload:
        return cls(
            x=float(data["x"]),
            y=float(data["y"]),
            userName=data.get("userName"),
            color=data.get("color"),
        )

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {"x": self.x, "y": self.y}
        if self.userName is not None:
            res["userName"] = self.userName
        if self.color is not None:
            res["color"] = self.color
        return res


# ==============================================================================
# Operations (Message Envelopes)
# ==============================================================================

TPayload = TypeVar("TPayload")


@dataclass
class BaseOperation(Generic[TPayload]):
    """Standard operation envelope common to all whiteboard events."""
    id: str
    payload: TPayload
    version: int
    userId: str
    type: str = ""
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> dict[str, Any]:
        payload_dict = (
            self.payload.to_dict()
            if hasattr(self.payload, "to_dict")
            else self.payload
        )
        return {
            "id": self.id,
            "type": self.type,
            "payload": payload_dict,
            "version": self.version,
            "userId": self.userId,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class ShapeAddOperation(BaseOperation[ShapeAddPayload]):
    type: str = OperationType.SHAPE_ADD.value

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShapeAddOperation:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            payload=ShapeAddPayload.from_dict(data["payload"]),
            version=int(data.get("version", 0)),
            userId=str(data.get("userId", "")),
            type=OperationType.SHAPE_ADD.value,
            timestamp=int(data.get("timestamp", int(time.time() * 1000))),
        )


@dataclass
class ShapeUpdateOperation(BaseOperation[ShapeUpdatePayload]):
    type: str = OperationType.SHAPE_UPDATE.value

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShapeUpdateOperation:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            payload=ShapeUpdatePayload.from_dict(data["payload"]),
            version=int(data.get("version", 0)),
            userId=str(data.get("userId", "")),
            type=OperationType.SHAPE_UPDATE.value,
            timestamp=int(data.get("timestamp", int(time.time() * 1000))),
        )


@dataclass
class ShapeRemoveOperation(BaseOperation[ShapeRemovePayload]):
    type: str = OperationType.SHAPE_REMOVE.value

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShapeRemoveOperation:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            payload=ShapeRemovePayload.from_dict(data["payload"]),
            version=int(data.get("version", 0)),
            userId=str(data.get("userId", "")),
            type=OperationType.SHAPE_REMOVE.value,
            timestamp=int(data.get("timestamp", int(time.time() * 1000))),
        )


@dataclass
class CursorMoveOperation(BaseOperation[CursorMovePayload]):
    type: str = OperationType.CURSOR_MOVE.value

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CursorMoveOperation:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            payload=CursorMovePayload.from_dict(data["payload"]),
            version=int(data.get("version", 0)),
            userId=str(data.get("userId", "")),
            type=OperationType.CURSOR_MOVE.value,
            timestamp=int(data.get("timestamp", int(time.time() * 1000))),
        )


# ==============================================================================
# Snapshot Message
# ==============================================================================

@dataclass
class SnapshotMessage:
    """Full board state sent to a newly joined client upon connection."""
    shapes: list[Shape] = field(default_factory=list)
    version: int = 0
    type: str = OperationType.SNAPSHOT.value

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SnapshotMessage:
        shapes = [Shape.from_dict(s) for s in data.get("shapes", [])]
        return cls(
            type=OperationType.SNAPSHOT.value,
            version=int(data.get("version", len(shapes))),
            shapes=shapes,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "version": self.version,
            "shapes": [shape.to_dict() for shape in self.shapes],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


# ==============================================================================
# Union & Parser Helpers
# ==============================================================================

WhiteboardOperation = Union[
    ShapeAddOperation,
    ShapeUpdateOperation,
    ShapeRemoveOperation,
    CursorMoveOperation,
]

WhiteboardMessage = Union[WhiteboardOperation, SnapshotMessage]


def parse_operation(data: Union[str, dict[str, Any]]) -> WhiteboardMessage:
    """
    Parses a raw JSON string or Python dictionary into its strongly-typed dataclass.
    """
    if isinstance(data, str):
        data = json.loads(data)

    msg_type = data.get("type")

    if msg_type == OperationType.SHAPE_ADD.value:
        return ShapeAddOperation.from_dict(data)
    elif msg_type == OperationType.SHAPE_UPDATE.value:
        return ShapeUpdateOperation.from_dict(data)
    elif msg_type == OperationType.SHAPE_REMOVE.value:
        return ShapeRemoveOperation.from_dict(data)
    elif msg_type == OperationType.CURSOR_MOVE.value:
        return CursorMoveOperation.from_dict(data)
    elif msg_type == OperationType.SNAPSHOT.value:
        return SnapshotMessage.from_dict(data)
    else:
        raise ValueError(f"Unknown whiteboard message type: {msg_type}")

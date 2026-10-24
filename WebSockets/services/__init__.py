"""
Services package for whiteboard collaboration.
Contains all domain logic, shape mutations, state management, and schemas.
"""

from .shape_service import ShapeService, shape_service
from .types import (
    BaseOperation,
    CursorMoveOperation,
    CursorMovePayload,
    OperationType,
    Point,
    Shape,
    ShapeAddOperation,
    ShapeAddPayload,
    ShapeRemoveOperation,
    ShapeRemovePayload,
    ShapeStyle,
    ShapeType,
    ShapeUpdateOperation,
    ShapeUpdatePayload,
    SnapshotMessage,
    WhiteboardMessage,
    WhiteboardOperation,
    parse_operation,
)
from .whiteboard_service import ProcessResult, WhiteboardService, whiteboard_service

__all__ = [
    # Types & Enums
    "OperationType",
    "ShapeType",
    "Point",
    "ShapeStyle",
    "Shape",
    "ShapeAddPayload",
    "ShapeUpdatePayload",
    "ShapeRemovePayload",
    "CursorMovePayload",
    "BaseOperation",
    "ShapeAddOperation",
    "ShapeUpdateOperation",
    "ShapeRemoveOperation",
    "CursorMoveOperation",
    "SnapshotMessage",
    "WhiteboardOperation",
    "WhiteboardMessage",
    "parse_operation",
    # Services
    "ShapeService",
    "shape_service",
    "WhiteboardService",
    "whiteboard_service",
    "ProcessResult",
]

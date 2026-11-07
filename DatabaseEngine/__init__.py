"""
DatabaseEngine package.
Exposes database engine and modular subservices.
"""

from .Engine import DatabaseEngine, db_engine
from .subservices import (
    SessionManager,
    UserService,
    WhiteboardRepository,
    session_manager,
    user_service,
    whiteboard_repository,
)

__all__ = [
    "DatabaseEngine",
    "db_engine",
    "UserService",
    "user_service",
    "SessionManager",
    "session_manager",
    "WhiteboardRepository",
    "whiteboard_repository",
]


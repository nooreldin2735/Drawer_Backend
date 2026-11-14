"""
WebSocket Consumer Interface Layer.
Acts strictly as a transport adapter between WebSockets/Channels and the domain services.
All state, shape manipulation, validation, and business logic are delegated to WebSockets.services.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from DatabaseEngine import db_engine
from .services import ProcessOperationRequest, whiteboard_service

logger = logging.getLogger(__name__)


class CanvasConsumer(AsyncWebsocketConsumer):
    """
    WebSocket transport interface for real-time collaborative whiteboard.
    Zero business logic: delegates all room resolution, snapshot building,
    and shape mutations to WhiteboardService and ShapeService.
    """

    async def connect(self):
        # 1. Resolve room, user identity, and invite code via domain service
        self.room_name, self.user_id = whiteboard_service.extract_room_info(self.scope)
        self.user_name, self.is_authenticated = whiteboard_service.extract_user_identity(self.scope)
        self.invite_code = whiteboard_service.extract_invite_code(self.scope)

        # 2. Access control: Validate that user/client joins via invite code (or as owner)
        user = self.scope.get("user")
        is_allowed, error_reason = await whiteboard_service.validate_session_access(
            board_id=self.room_name,
            invite_code=self.invite_code,
            user=user,
        )

        if not is_allowed:
            logger.warning(
                "WebSocket connection rejected for room '%s' (user: %s): %s",
                self.room_name,
                self.user_name,
                error_reason,
            )
            # Accept temporarily to dispatch error message then close with 4003
            await self.accept()
            await self.send(
                text_data=json.dumps({
                    "type": "error",
                    "code": 4003,
                    "message": error_reason or "Joining session requires a valid invite code.",
                })
            )
            await self.close(code=4003)
            return

        self.room_group_name = whiteboard_service.get_group_name(self.room_name)

        # 3. Join the channel layer group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # 4. Track active session participant in DatabaseEngine
        await db_engine.register_session_participant(
            board_id=self.room_name,
            channel_name=self.channel_name,
            user=user,
            display_name=self.user_name,
        )

        # 5. Accept WebSocket connection
        await self.accept()

        # 6. Request initial snapshot from service (loads from PostgreSQL if needed)
        snapshot = await whiteboard_service.get_initial_snapshot(self.room_name)
        await self.send(text_data=snapshot.to_json())

    async def disconnect(self, close_code):
        if not hasattr(self, "room_group_name"):
            return

        # 1. Unregister participant from DatabaseEngine session manager
        board_id, is_empty, remaining = await db_engine.unregister_session_participant(self.channel_name)

        # 2. Session closure: persist durable drawing state to PostgreSQL via DatabaseEngine
        try:
            await whiteboard_service.save_session_closure(
                board_id=self.room_name,
                user=self.scope.get("user"),
                saved_by_name=self.user_name,
            )
        except Exception as exc:
            logger.warning("Could not persist session closure for board %s: %s", self.room_name, exc)

        # 3. Leave channel layer group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        print(text_data)
        # Delegate validation, shape mutations, and payload packaging to service
        request = ProcessOperationRequest(
            board_id=self.room_name,
            raw_data=text_data,
            sender_channel_name=self.channel_name,
        )
        result = await whiteboard_service.process_operation(request)

        # Send direct response back to this client if required (e.g. snapshot, ack)
        if result.direct_response:
            await self.send(text_data=json.dumps(result.direct_response))

        # Broadcast operation to all other room participants
        if result.broadcast_data:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "canvas_message",
                    "message": result.broadcast_data,
                    "sender_channel_name": self.channel_name,
                }
            )

    async def canvas_message(self, event):
        """
        Deliver broadcast event from channel layer to the connected client.
        Suppresses self-echo if sender_channel_name matches.
        """
        if event.get("sender_channel_name") == self.channel_name:
            return

        message = event.get("message")
        if message:
            await self.send(text_data=json.dumps(message))


class EchoConsumer(AsyncWebsocketConsumer):
    """Simple echo interface for connection smoke tests."""

    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            await self.send(text_data=f"Echo: {text_data}")

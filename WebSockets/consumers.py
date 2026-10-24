"""
WebSocket Consumer Interface Layer.
Acts strictly as a transport adapter between WebSockets/Channels and the domain services.
All state, shape manipulation, validation, and business logic are delegated to WebSockets.services.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from .services import whiteboard_service

logger = logging.getLogger(__name__)


class CanvasConsumer(AsyncWebsocketConsumer):
    """
    WebSocket transport interface for real-time collaborative whiteboard.
    Zero business logic: delegates all room resolution, snapshot building,
    and shape mutations to WhiteboardService and ShapeService.
    """

    async def connect(self):
        # 1. Resolve room and user info via domain service
        self.room_name, self.user_id = whiteboard_service.extract_room_info(self.scope)
        self.room_group_name = whiteboard_service.get_group_name(self.room_name)

        # 2. Join the channel layer group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # 3. Accept WebSocket connection
        await self.accept()

        # 4. Request initial snapshot from service and deliver to the client
        snapshot = await whiteboard_service.get_initial_snapshot(self.room_name)
        await self.send(text_data=snapshot.to_json())

    async def disconnect(self, close_code):
        # Leave channel layer group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        print(text_data)
        # Delegate validation, shape mutations, and payload packaging to service
        result = await whiteboard_service.process_operation(
            board_id=self.room_name,
            raw_data=text_data,
            sender_channel_name=self.channel_name,
        )

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

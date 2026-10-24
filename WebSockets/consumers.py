import json
from channels.generic.websocket import AsyncWebsocketConsumer


class CanvasConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time collaborative canvas/whiteboard events.
    Supports joining room-specific channel layer groups and broadcasting messages.
    """

    async def connect(self):
        # Extract room_name from URL kwargs (or default to 'default')
        self.room_name = self.scope["url_route"]["kwargs"].get("room_name", "default")
        self.room_group_name = f"canvas_{self.room_name}"

        # Join the room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave the room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data=None, bytes_data=None):
        """
        Receive message from WebSocket client and broadcast it to the room group.
        """
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            data = {"raw": text_data}

        # Broadcast the payload to everyone in the room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "canvas_message",
                "message": data,
                "sender_channel_name": self.channel_name,
            }
        )

    async def canvas_message(self, event):
        """
        Handler invoked when a message is received from the room group.
        Sends the payload to the connected WebSocket client.
        """
        message = event["message"]

        # Option: skip echoing back to sender if desired, e.g.:
        # if event.get("sender_channel_name") == self.channel_name:
        #     return

        await self.send(text_data=json.dumps(message))


class EchoConsumer(AsyncWebsocketConsumer):
    """
    A lightweight consumer that echoes received messages back to the sender.
    Useful for health checks and connection testing.
    """

    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            await self.send(text_data=f"Echo: {text_data}")

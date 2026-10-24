from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Room-based canvas websocket endpoint (e.g., ws://localhost:8000/ws/canvas/room1/)
    re_path(r"^ws/canvas/(?P<room_name>[\w-]+)/$", consumers.CanvasConsumer.as_asgi()),
    # Default canvas endpoint (e.g., ws://localhost:8000/ws/canvas/)
    re_path(r"^ws/canvas/$", consumers.CanvasConsumer.as_asgi()),
    # Simple echo test endpoint (e.g., ws://localhost:8000/ws/echo/)
    re_path(r"^ws/echo/$", consumers.EchoConsumer.as_asgi()),
]

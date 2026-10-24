from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Handshake endpoint matching BACKEND_SPEC.md: ws://<host>:<port>/ws?boardId=<boardId>
    re_path(r"^ws/?$", consumers.CanvasConsumer.as_asgi()),
    # Room-based path endpoint: ws://<host>:<port>/ws/canvas/<room_name>/
    re_path(r"^ws/canvas/(?P<room_name>[\w-]+)/?$", consumers.CanvasConsumer.as_asgi()),
    # Default canvas path endpoint: ws://<host>:<port>/ws/canvas/?$
    re_path(r"^ws/canvas/?$", consumers.CanvasConsumer.as_asgi()),
    # Simple echo test endpoint: ws://<host>:<port>/ws/echo/
    re_path(r"^ws/echo/?$", consumers.EchoConsumer.as_asgi()),
]

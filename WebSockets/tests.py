import json
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import TransactionTestCase
from CanvasDrawerProject.asgi import application
from Dashboard.models import Whiteboard


class WebSocketInviteCodeTests(TransactionTestCase):
    async def test_websocket_connection_rejected_without_invite_code(self):
        wb = await Whiteboard.objects.acreate(
            id="ws-board-1",
            title="WS Private Board",
        )
        communicator = WebsocketCommunicator(
            application,
            f"/ws/canvas/{wb.id}/?boardId={wb.id}",
        )
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        # Verify rejection message
        response = await communicator.receive_json_from()
        self.assertEqual(response.get("type"), "error")
        self.assertEqual(response.get("code"), 4003)
        await communicator.disconnect()

    async def test_websocket_connection_rejected_with_invalid_invite_code(self):
        wb = await Whiteboard.objects.acreate(
            id="ws-board-2",
            title="WS Private Board 2",
        )
        communicator = WebsocketCommunicator(
            application,
            f"/ws/canvas/{wb.id}/?boardId={wb.id}&inviteCode=WRONGCODE",
        )
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        response = await communicator.receive_json_from()
        self.assertEqual(response.get("type"), "error")
        self.assertEqual(response.get("code"), 4003)
        await communicator.disconnect()

    async def test_websocket_connection_accepted_with_valid_invite_code(self):
        wb = await Whiteboard.objects.acreate(
            id="ws-board-3",
            title="WS Shared Board",
        )
        communicator = WebsocketCommunicator(
            application,
            f"/ws/canvas/{wb.id}/?boardId={wb.id}&inviteCode={wb.invite_code}",
        )
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        # Should receive initial snapshot
        response = await communicator.receive_json_from()
        self.assertEqual(response.get("type"), "snapshot")
        await communicator.disconnect()

    async def test_websocket_connection_with_board_owner(self):
        owner = await User.objects.acreate_user(username="boardowner", password="password123")
        wb = await Whiteboard.objects.acreate(
            id="ws-board-4",
            title="Owner Board",
            owner=owner,
        )
        communicator = WebsocketCommunicator(
            application,
            f"/ws/canvas/{wb.id}/?boardId={wb.id}&inviteCode={wb.invite_code}",
        )
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        response = await communicator.receive_json_from()
        self.assertEqual(response.get("type"), "snapshot")
        await communicator.disconnect()


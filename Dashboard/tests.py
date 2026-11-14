import base64
import json
from django.contrib.auth.models import User
from django.test import TestCase, Client
from Dashboard.models import Whiteboard
from DatabaseEngine import db_engine


class AuthAndInviteCodeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice",
            password="alicepassword123",
            email="alice@example.com",
        )

    def test_user_registration_success(self):
        response = self.client.post(
            "/api/dashboard/auth/register/",
            data=json.dumps({"username": "bob", "password": "bobpassword123"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["user"]["username"], "bob")
        self.assertTrue(data["user"]["is_authenticated"])

    def test_user_registration_duplicate_username(self):
        response = self.client.post(
            "/api/dashboard/auth/register/",
            data=json.dumps({"username": "alice", "password": "password456"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)

    def test_user_login_json(self):
        response = self.client.post(
            "/api/dashboard/auth/login/",
            data=json.dumps({"username": "alice", "password": "alicepassword123"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["user"]["username"], "alice")

    def test_user_login_invalid_password(self):
        response = self.client.post(
            "/api/dashboard/auth/login/",
            data=json.dumps({"username": "alice", "password": "wrongpassword"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_http_basic_auth_header(self):
        creds = base64.b64encode(b"alice:alicepassword123").decode("utf-8")
        response = self.client.get(
            "/api/dashboard/me/",
            HTTP_AUTHORIZATION=f"Basic {creds}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("is_authenticated"))
        self.assertEqual(data.get("username"), "alice")

    def test_user_logout(self):
        self.client.login(username="alice", password="alicepassword123")
        response = self.client.post("/api/dashboard/auth/logout/")
        self.assertEqual(response.status_code, 200)

        me_resp = self.client.get("/api/dashboard/me/")
        self.assertFalse(me_resp.json().get("is_authenticated"))

    def test_create_whiteboard_generates_invite_code(self):
        self.client.login(username="alice", password="alicepassword123")
        response = self.client.post(
            "/api/dashboard/whiteboards/",
            data=json.dumps({"title": "Design Whiteboard"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(bool(data.get("invite_code")))
        self.assertEqual(data.get("owner"), "alice")

    def test_join_whiteboard_with_valid_invite_code(self):
        wb = Whiteboard.objects.create(
            id="test-board-123",
            title="Shared Architecture Board",
            owner=self.user,
        )
        invite_code = wb.invite_code

        # Another unauthenticated or separate client joins via invite code
        join_client = Client()
        response = join_client.post(
            "/api/dashboard/whiteboards/join/",
            data=json.dumps({"invite_code": invite_code}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["whiteboard"]["id"], "test-board-123")

    def test_join_whiteboard_with_invalid_invite_code(self):
        join_client = Client()
        response = join_client.post(
            "/api/dashboard/whiteboards/join/",
            data=json.dumps({"invite_code": "NON_EXISTENT_CODE"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("error", data)

    def test_whiteboard_detail_access_restrictions(self):
        wb = Whiteboard.objects.create(
            id="secret-board-99",
            title="Private Team Board",
            owner=self.user,
        )
        invite_code = wb.invite_code

        guest_client = Client()

        # Direct access without invite code is blocked
        resp_blocked = guest_client.get(f"/api/dashboard/whiteboards/{wb.id}/")
        self.assertEqual(resp_blocked.status_code, 403)

        # Access with valid invite code is allowed
        resp_allowed = guest_client.get(f"/api/dashboard/whiteboards/{wb.id}/?invite_code={invite_code}")
        self.assertEqual(resp_allowed.status_code, 200)
        self.assertEqual(resp_allowed.json()["id"], wb.id)

        # Owner can access without invite code
        self.client.login(username="alice", password="alicepassword123")
        resp_owner = self.client.get(f"/api/dashboard/whiteboards/{wb.id}/")
        self.assertEqual(resp_owner.status_code, 200)

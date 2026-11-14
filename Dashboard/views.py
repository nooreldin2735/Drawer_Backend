import base64
import json
import logging
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpRequest, HttpResponseBadRequest, HttpResponseNotFound
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from DatabaseEngine import db_engine
from .models import Whiteboard

logger = logging.getLogger(__name__)


def _extract_credentials(request: HttpRequest) -> tuple[str, str]:
    """
    Extracts username and password from either:
    1. HTTP Basic Authorization header
    2. JSON request body
    """
    # 1. Check HTTP Basic Auth header
    auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.startswith("Basic "):
        try:
            encoded = auth_header.split(" ", 1)[1].strip()
            decoded = base64.b64decode(encoded).decode("utf-8")
            if ":" in decoded:
                username, password = decoded.split(":", 1)
                return username.strip(), password
        except Exception as exc:
            logger.debug("Failed to decode Basic auth header: %s", exc)

    # 2. Check JSON request body
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
        username = str(body.get("username", "")).strip()
        password = str(body.get("password", ""))
        return username, password
    except Exception:
        return "", ""


@csrf_exempt
@require_http_methods(["POST"])
def auth_login_view(request: HttpRequest) -> JsonResponse:
    """
    POST: Authenticates user via basic credentials or JSON body,
    creates a session cookie, and returns user identity.
    """
    username, password = _extract_credentials(request)
    if not username or not password:
        return JsonResponse({"error": "Username and password are required"}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"error": "Invalid username or password"}, status=401)

    login(request, user)
    return JsonResponse({
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_authenticated": True,
        },
    })


@csrf_exempt
@require_http_methods(["POST"])
def auth_register_view(request: HttpRequest) -> JsonResponse:
    """
    POST: Registers a new user account with basic authentication credentials,
    automatically logs them in, and returns user identity.
    """
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        body = {}

    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    email = str(body.get("email", "")).strip()

    if not username:
        return JsonResponse({"error": "Username is required"}, status=400)
    if len(username) < 3:
        return JsonResponse({"error": "Username must be at least 3 characters"}, status=400)
    if not password:
        return JsonResponse({"error": "Password is required"}, status=400)
    if len(password) < 4:
        return JsonResponse({"error": "Password must be at least 4 characters"}, status=400)

    if User.objects.filter(username__iexact=username).exists():
        return JsonResponse({"error": f"Username '{username}' is already taken"}, status=400)

    try:
        user = User.objects.create_user(username=username, password=password, email=email)
        login(request, user)
        return JsonResponse({
            "success": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_authenticated": True,
            },
        }, status=201)
    except Exception as exc:
        logger.error("Error creating user: %s", exc)
        return JsonResponse({"error": "Failed to create user account"}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def auth_logout_view(request: HttpRequest) -> JsonResponse:
    """
    POST: Logs out the current user and clears session.
    """
    logout(request)
    return JsonResponse({"success": True, "message": "Logged out successfully"})


@csrf_exempt
@require_http_methods(["POST"])
def whiteboard_join_view(request: HttpRequest) -> JsonResponse:
    """
    POST: Join an existing session strictly via invite code.
    Verifies that the invite code matches an active whiteboard session.
    """
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        body = {}

    invite_code = str(body.get("invite_code", "")).strip().upper()
    if not invite_code:
        return JsonResponse({"error": "Invite code is required to join a session"}, status=400)

    wb = db_engine.get_whiteboard_by_invite_code(invite_code)
    if not wb:
        return JsonResponse(
            {"error": "Invalid or expired invite code. Please check the code and try again."},
            status=404,
        )

    return JsonResponse({
        "success": True,
        "whiteboard": wb,
        "message": "Successfully joined whiteboard session",
    })


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whiteboards_collection_view(request: HttpRequest) -> JsonResponse:
    """
    GET: List whiteboards owned by the user (or available guest drawings).
    POST: Create a new whiteboard session with generated invite code.
    """
    user = request.user if request.user.is_authenticated else None
    guest_name = request.GET.get("guest_name", "Guest")

    if request.method == "GET":
        whiteboards = db_engine.get_user_whiteboards(user=user, guest_name=guest_name)
        return JsonResponse({"whiteboards": whiteboards, "count": len(whiteboards)})

    # POST: Create whiteboard
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        body = {}

    title = body.get("title", "").strip() or "Untitled Whiteboard"
    board_id = body.get("id", "").strip() or None
    guest = body.get("guest_name", guest_name)

    created_wb = db_engine.create_whiteboard(
        title=title,
        board_id=board_id,
        user=user,
        guest_name=guest,
    )
    return JsonResponse(created_wb, status=201)


@csrf_exempt
@require_http_methods(["GET", "DELETE"])
def whiteboard_detail_view(request: HttpRequest, board_id: str) -> JsonResponse:
    """
    GET: Retrieve whiteboard details and drawing snapshot.
         Enforces that access requires owner identity OR valid invite code.
    DELETE: Delete a whiteboard session.
    """
    user = request.user if request.user.is_authenticated else None

    if request.method == "GET":
        invite_code = request.GET.get("invite_code") or request.GET.get("inviteCode") or ""
        is_allowed, wb, reason = db_engine.verify_session_access(
            board_id=board_id,
            invite_code=invite_code.strip().upper(),
            user=user,
        )
        if not wb:
            return JsonResponse({"error": "Whiteboard not found"}, status=404)
        if not is_allowed:
            return JsonResponse(
                {"error": "Access denied. You can only join this session via a valid invite code."},
                status=403,
            )
        return JsonResponse(wb)

    # DELETE
    success = db_engine.delete_whiteboard(board_id, user=user)
    if not success:
        return JsonResponse({"error": "Failed to delete whiteboard or board not found"}, status=400)
    return JsonResponse({"success": True, "message": f"Whiteboard {board_id} deleted"})


@require_http_methods(["GET"])
def whiteboard_versions_view(request: HttpRequest, board_id: str) -> JsonResponse:
    """
    GET: Retrieves version history checkpoints for a whiteboard.
    Supports versioning and inspection of previous states.
    """
    versions = db_engine.get_versions(board_id)
    return JsonResponse({"board_id": board_id, "versions": versions, "count": len(versions)})


@csrf_exempt
@require_http_methods(["POST"])
def whiteboard_restore_version_view(request: HttpRequest, board_id: str, version_number: int) -> JsonResponse:
    """
    POST: Rollback / restore a whiteboard to a specific version number.
    """
    restored = db_engine.restore_version(board_id, version_number)
    if not restored:
        return JsonResponse({"error": f"Version {version_number} not found for board {board_id}"}, status=404)
    return JsonResponse({"success": True, "whiteboard": restored})


@require_http_methods(["GET"])
def current_user_view(request: HttpRequest) -> JsonResponse:
    """
    GET: Returns current user identity.
    If authenticated, returns username and user metadata.
    If unauthenticated, returns 'Guest'.
    """
    if request.user.is_authenticated:
        return JsonResponse({
            "is_authenticated": True,
            "username": request.user.username,
            "email": request.user.email,
            "id": request.user.id,
        })
    return JsonResponse({
        "is_authenticated": False,
        "username": "Guest",
        "email": "",
        "id": None,
    })

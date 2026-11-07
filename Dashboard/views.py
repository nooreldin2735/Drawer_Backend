import json
from django.http import JsonResponse, HttpRequest, HttpResponseBadRequest, HttpResponseNotFound
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from DatabaseEngine import db_engine


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whiteboards_collection_view(request: HttpRequest) -> JsonResponse:
    """
    GET: List all whiteboards / previous drawings.
    POST: Create a new whiteboard session.
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
    GET: Retrieve whiteboard details and latest drawing snapshot.
    DELETE: Delete a whiteboard session.
    """
    user = request.user if request.user.is_authenticated else None

    if request.method == "GET":
        wb = db_engine.get_whiteboard_details(board_id)
        if not wb:
            return JsonResponse({"error": "Whiteboard not found"}, status=404)
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
    If authenticated, returns username.
    If unauthenticated, returns 'Guest'.
    """
    if request.user.is_authenticated:
        return JsonResponse({
            "is_authenticated": True,
            "username": request.user.username,
            "id": request.user.id,
        })
    return JsonResponse({
        "is_authenticated": False,
        "username": "Guest",
        "id": None,
    })

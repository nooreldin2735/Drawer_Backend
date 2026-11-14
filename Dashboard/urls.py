from django.urls import path
from . import views

urlpatterns = [
    # Basic Authentication endpoints
    path("auth/login/", views.auth_login_view, name="auth_login"),
    path("auth/register/", views.auth_register_view, name="auth_register"),
    path("auth/logout/", views.auth_logout_view, name="auth_logout"),
    path("auth/me/", views.current_user_view, name="auth_me"),

    # User identity (retained for backward compatibility)
    path("me/", views.current_user_view, name="current_user"),

    # Join session strictly via invite code
    path("whiteboards/join/", views.whiteboard_join_view, name="whiteboard_join"),

    # Whiteboard collection (list / create)
    path("whiteboards/", views.whiteboards_collection_view, name="whiteboards_collection"),

    # Whiteboard detail (get / delete)
    path("whiteboards/<str:board_id>/", views.whiteboard_detail_view, name="whiteboard_detail"),

    # Versioning endpoints
    path("whiteboards/<str:board_id>/versions/", views.whiteboard_versions_view, name="whiteboard_versions"),
    path(
        "whiteboards/<str:board_id>/restore/<int:version_number>/",
        views.whiteboard_restore_version_view,
        name="whiteboard_restore_version",
    ),
]


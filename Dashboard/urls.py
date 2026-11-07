from django.urls import path
from . import views

urlpatterns = [
    # User identity
    path("me/", views.current_user_view, name="current_user"),
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


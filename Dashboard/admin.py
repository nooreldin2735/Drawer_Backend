from django.contrib import admin
from .models import Whiteboard, WhiteboardVersion


@admin.register(Whiteboard)
class WhiteboardAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "owner", "guest_name", "version", "updated_at", "last_closed_at")
    search_fields = ("id", "title", "owner__username", "guest_name")
    list_filter = ("is_active", "created_at", "updated_at")


@admin.register(WhiteboardVersion)
class WhiteboardVersionAdmin(admin.ModelAdmin):
    list_display = ("whiteboard", "version_number", "saved_by", "note", "created_at")
    list_filter = ("created_at", "saved_by")

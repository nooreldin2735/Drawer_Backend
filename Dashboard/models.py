import secrets
import uuid
from django.db import models
from django.contrib.auth.models import User


def generate_invite_code() -> str:
    """Generate a unique uppercase 8-character invite code (e.g. 8A3F1B2C)."""
    return secrets.token_hex(4).upper()


class Whiteboard(models.Model):
    """
    Persistent whiteboard entity storing room metadata and current canvas state JSON.
    Reflects the latest drawing changes on the dashboard.
    """
    id = models.CharField(max_length=128, primary_key=True)
    title = models.CharField(max_length=255, default="Untitled Whiteboard")
    invite_code = models.CharField(
        max_length=32,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Unique invite code required to join this whiteboard session",
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whiteboards",
    )
    guest_name = models.CharField(max_length=100, default="Guest", blank=True)
    snapshot = models.JSONField(
        default=dict,
        help_text="Stores the latest drawing shapes JSON and metadata to reflect changes in the dashboard",
    )
    version = models.IntegerField(default=0, help_text="Monotonic version counter for sync and versioning")
    thumbnail = models.TextField(blank=True, null=True, help_text="Optional base64 preview")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Whiteboard"
        verbose_name_plural = "Whiteboards"

    def __str__(self):
        return f"{self.title} ({self.id}) [v{self.version}]"

    def save(self, *args, **kwargs):
        if not self.invite_code:
            code = generate_invite_code()
            while Whiteboard.objects.filter(invite_code=code).exists():
                code = generate_invite_code()
            self.invite_code = code
        super().save(*args, **kwargs)

    def to_dict(self):
        shapes = self.snapshot.get("shapes", []) if isinstance(self.snapshot, dict) else []
        owner_name = None
        if self.owner_id is not None:
            try:
                owner_name = self.owner.username if self.owner else None
            except Exception:
                owner_name = None

        return {
            "id": self.id,
            "title": self.title,
            "invite_code": self.invite_code,
            "owner": owner_name,
            "guest_name": self.guest_name,
            "display_user": owner_name or self.guest_name,
            "shape_count": len(shapes),
            "version": self.version,
            "snapshot": self.snapshot,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_closed_at": self.last_closed_at.isoformat() if self.last_closed_at else None,
        }


class WhiteboardVersion(models.Model):
    """
    Historical snapshot of a whiteboard at a session checkpoint.
    Supports version history and rollback to previous drawings.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    whiteboard = models.ForeignKey(
        Whiteboard,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.IntegerField()
    snapshot = models.JSONField(default=dict)
    saved_by = models.CharField(max_length=150, default="Guest")
    note = models.CharField(max_length=255, blank=True, default="Session closed checkpoint")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number"]
        unique_together = ("whiteboard", "version_number")
        verbose_name = "Whiteboard Version"
        verbose_name_plural = "Whiteboard Versions"

    def __str__(self):
        return f"{self.whiteboard.title} - Version {self.version_number}"

    def to_dict(self):
        shapes = self.snapshot.get("shapes", []) if isinstance(self.snapshot, dict) else []
        return {
            "id": str(self.id),
            "whiteboard_id": self.whiteboard_id,
            "version_number": self.version_number,
            "saved_by": self.saved_by,
            "note": self.note,
            "shape_count": len(shapes),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

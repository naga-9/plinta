"""What happened, to what, by whom.

One row per write. The diff is stored as it arrived on the event, because core
computed it while performing the write and is the only thing that knew both
values (§4.2).
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Action(models.TextChoices):
    CREATED = "created", "Created"
    UPDATED = "updated", "Updated"
    DELETED = "deleted", "Deleted"
    STATE_CHANGED = "state_changed", "State changed"


class AuditEntry(models.Model):
    """One recorded write.

    The target is a generic relation **and** a stored label, because a deleted
    row leaves the relation dangling and an audit trail that forgets what it
    was about is not one. The label is what survives.
    """

    action = models.CharField(max_length=20, choices=Action)
    at = models.DateTimeField(auto_now_add=True, db_index=True)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_entries",
        help_text="Null when nothing was signed in — an importer, a command.",
    )
    #: What performed the write, from the event's envelope.
    source = models.CharField(max_length=60, blank=True, default="")

    content_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.SET_NULL
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    target = GenericForeignKey("content_type", "object_id")
    #: What the row was, in words, at the moment it was written about.
    target_label = models.CharField(max_length=200, blank=True, default="")

    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text="{field: [before, after]}, as the event carried it.",
    )

    class Meta:
        ordering = ["-at", "-pk"]
        verbose_name_plural = "audit entries"
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self) -> str:
        return f"{self.get_action_display()} {self.target_label or self.content_type}"

    @property
    def fields_changed(self) -> list[str]:
        """Which fields moved, for a screen that lists them."""
        return sorted(self.changes)

"""What was sent, to whom, and what is still waiting to go.

Email is a **queue**, never an inline send: a mail server that is down must not
be able to fail somebody's save.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """One thing somebody should know about.

    ``kind`` is the registration's name (§14.6), which is what a preference is
    keyed on — so a person mutes *sales recorded* rather than *notifications*.
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=60, db_index=True)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="")
    url = models.CharField(
        max_length=300, blank=True, default="", help_text="Where it takes you."
    )

    content_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.SET_NULL
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    target = GenericForeignKey("content_type", "object_id")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["recipient", "read_at"])]

    def __str__(self) -> str:
        return self.title

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def mark_read(self) -> None:
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])


class EmailStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"


class QueuedEmail(models.Model):
    """A message waiting for the delivery command.

    Queued rather than sent inline, so a mail outage delays a notification
    instead of failing the write that caused it.
    """

    to = models.EmailField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    kind = models.CharField(max_length=60, blank=True, default="")

    status = models.CharField(
        max_length=10, choices=EmailStatus, default=EmailStatus.QUEUED, db_index=True
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")

    queued_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["queued_at", "pk"]

    def __str__(self) -> str:
        return f"{self.subject} → {self.to}"


class NotificationPreference(models.Model):
    """One person's answer for one kind.

    A row exists only where somebody has expressed a preference; the
    registration's own defaults apply otherwise, so a new kind does not need a
    row per user before it works.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    kind = models.CharField(max_length=60)
    in_app = models.BooleanField(default=True)
    email = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "kind"], name="unique_preference_per_kind"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user}: {self.kind}"

"""A comment, and who may read it.

Soft-deleted rather than removed: a thread with a hole in it reads as a bug,
and a reply that answers a vanished remark reads as nonsense.
"""
from __future__ import annotations

import re

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

#: `@name` in a body. Deliberately conservative: a username with a dot or a
#: hyphen is matched, an email address in the text is not.
MENTION = re.compile(r"(?<![\w@])@([\w][\w.-]{0,58}[\w])")


class CommentQuerySet(models.QuerySet):
    def alive(self):
        """Comments that have not been withdrawn."""
        return self.filter(deleted_at__isnull=True)

    def on(self, obj):
        """The thread attached to one row."""
        return self.filter(
            content_type=ContentType.objects.get_for_model(type(obj)),
            object_id=obj.pk,
        )


class Comment(models.Model):
    """One remark, attached to any row by content type."""

    body = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="comments",
    )

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")

    #: A reply. One level: a thread that nests without limit is a thread
    #: nobody can follow, and the parent is enough to group a conversation.
    reply_to = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )

    posted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = CommentQuerySet.as_manager()

    class Meta:
        ordering = ["posted_at", "pk"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self) -> str:
        return self.body[:60]

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def withdraw(self) -> None:
        """Hide the body, keep the row.

        A thread with a hole in it reads as a bug, and a reply answering a
        vanished remark reads as nonsense — so the shape of the conversation
        survives what was said.
        """
        if self.deleted_at is None:
            self.deleted_at = timezone.now()
            self.save(update_fields=["deleted_at"])

    def mentions(self) -> list[str]:
        """The usernames named in the body, in the order they appear."""
        seen, found = set(), []
        for name in MENTION.findall(self.body or ""):
            if name not in seen:
                seen.add(name)
                found.append(name)
        return found

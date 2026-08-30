"""Posting, editing and withdrawing — the one path that writes a comment.

Posting is where `comment_posted` is emitted, and it is emitted **after** the
row exists, so a listener that reads it finds something there.

This app resolves who was mentioned and puts them on the event. It does not
notify them: whether a mention becomes an email, a Discord message or nothing
is `notifications`' question, and asking it here is what made notifications
mandatory for anyone who wanted comments.
"""
from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from plinta.events import signals


class CommentDenied(Exception):
    """The user may not comment here, or may not touch this comment."""


def resolve_mentions(names: list[str]) -> list[Any]:
    """The users behind `@name`, ignoring the ones that match nobody.

    A typo is not an error: a comment reading "@teh-team" is still a comment,
    and refusing to post it would be a worse answer than nobody being told.
    """
    if not names:
        return []
    User = get_user_model()
    field = User.USERNAME_FIELD
    return list(User.objects.filter(**{f"{field}__in": names}))


def post(target: Any, body: str, author, *, reply_to=None, source: str = "") -> Any:
    """Add a comment to ``target`` and announce it.

    Raises:
        CommentDenied: the author may not view the row they are commenting on.
            Commenting is a way of reading a record out loud, so it cannot be
            open to somebody who may not read it.
    """
    from plinta.contrib.comments.models import Comment
    from plinta.permissions import can

    if not body or not body.strip():
        raise CommentDenied("a comment needs a body")
    if not can(author, "view", target):
        raise CommentDenied("may not comment on a row you may not see")
    if reply_to is not None and reply_to.reply_to_id is not None:
        # One level. A thread that nests without limit is one nobody follows.
        reply_to = reply_to.reply_to

    comment = Comment.objects.create(
        body=body.strip(),
        author=author if getattr(author, "pk", None) else None,
        content_type=ContentType.objects.get_for_model(type(target)),
        object_id=target.pk,
        reply_to=reply_to,
    )

    signals.emit_comment_posted(
        target,
        actor=author,
        body=comment.body,
        metadata={
            "comment_id": comment.pk,
            "mentioned": [u.pk for u in resolve_mentions(comment.mentions())],
            "reply_to": reply_to.pk if reply_to else None,
        },
        source=source,
    )
    return comment


def edit(comment: Any, body: str, editor) -> Any:
    """Change what a comment says.

    No event: a correction is not a new remark, and announcing one would
    notify a thread every time somebody fixed a typo.

    Raises:
        CommentDenied: the editor did not write it.
    """
    from plinta.permissions import can

    if not body or not body.strip():
        raise CommentDenied("a comment needs a body")
    if not can(editor, "change", comment):
        raise CommentDenied("may not edit somebody else's comment")
    comment.body = body.strip()
    comment.edited_at = timezone.now()
    comment.save(update_fields=["body", "edited_at"])
    return comment


def withdraw(comment: Any, actor) -> Any:
    """Hide a comment's body, keeping its place in the thread.

    Raises:
        CommentDenied: the actor may not delete it.
    """
    from plinta.permissions import can

    if not can(actor, "delete", comment):
        raise CommentDenied("may not withdraw this comment")
    comment.withdraw()
    return comment


def thread(target: Any, user) -> list[Any]:
    """The conversation on one row, oldest first.

    Withdrawn comments are included — a reply answering a gap reads as
    nonsense — and it is the template's business to draw them as withdrawn.
    """
    from plinta.contrib.comments.models import Comment
    from plinta.permissions import allowed

    return list(
        allowed(user, "view", Comment.objects.on(target)).select_related("author")
    )

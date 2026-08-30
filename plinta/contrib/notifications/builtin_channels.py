"""The two channels this app ships.

Both go through `register_channel`, the same door a Discord package would use.
If they had a private path into delivery, only the private path would stay
working — the argument ADR 0005 makes for components, applied here.
"""
from __future__ import annotations

from django.contrib.contenttypes.models import ContentType

from plinta.contrib.notifications.channels import register_channel


def deliver_in_app(user, notification, subscription=None, **kwargs) -> None:
    """A row in the recipient's list."""
    from plinta.contrib.notifications.models import Notification

    target = notification.target
    Notification.objects.create(
        recipient=user,
        kind=notification.kind,
        title=notification.title,
        body=notification.body,
        url=notification.url,
        content_type=ContentType.objects.get_for_model(type(target)) if target else None,
        object_id=getattr(target, "pk", None),
    )


def deliver_email(user, notification, subscription=None, **kwargs) -> None:
    """A row in the queue, not a message on the wire.

    Sending here would put a mail server's availability inside somebody's
    save. `send_queued_email` delivers it on a schedule instead.
    """
    from plinta.contrib.notifications.models import QueuedEmail

    QueuedEmail.objects.create(
        to=user.email,
        subject=notification.title,
        body=notification.body or notification.title,
        kind=notification.kind,
    )


def register() -> None:
    """Register both. Called from `AppConfig.ready()`."""
    register_channel(
        "in_app", "In the app", deliver=deliver_in_app, on_by_default=True
    )
    register_channel(
        "email",
        "Email",
        deliver=deliver_email,
        available=lambda user, **kw: bool(getattr(user, "email", "")),
        # Off unless asked for: a fresh install that mails everybody is one
        # nobody keeps.
        on_by_default=False,
    )

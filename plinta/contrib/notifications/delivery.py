"""Turning a subscription into rows: who hears, in app and by email.

Nothing here sends anything. A notification is a row and an email is a queued
row, because a mail server that is unreachable must not be able to fail the
write that caused the notification.
"""
from __future__ import annotations

import logging
from typing import Any

from django.contrib.contenttypes.models import ContentType

from plinta.contrib.notifications.registry import Subscription, for_event

logger = logging.getLogger(__name__)


def resolve(value: Any, obj: Any, payload: dict[str, Any]) -> str:
    """A title, body or URL: a plain string, or a callable given the event."""
    if callable(value):
        return str(value(obj, **payload) or "")
    return str(value or "")


def recipients_of(subscription: Subscription, obj: Any, payload: dict[str, Any]) -> list:
    """Who should hear about this, with the actor removed unless asked for.

    Telling somebody what they just did is noise, and it is the single most
    common complaint about a notification system — so it is off unless a
    subscription says otherwise.
    """
    try:
        people = list(subscription.recipients(obj, **payload) or [])
    except Exception:  # noqa: BLE001 - a consumer's callable is not ours to trust
        logger.exception("recipients for %r failed", subscription.name)
        return []

    actor = payload.get("actor")
    if not subscription.notify_actor and actor is not None:
        people = [p for p in people if getattr(p, "pk", None) != getattr(actor, "pk", None)]
    # A recipient listed twice is one notification, not two.
    seen, unique = set(), []
    for person in people:
        pk = getattr(person, "pk", None)
        if pk is not None and pk not in seen:
            seen.add(pk)
            unique.append(person)
    return unique


def wants(user, subscription: Subscription) -> tuple[bool, bool]:
    """Whether this person wants it in app, and by email.

    A stored preference wins; otherwise the subscription's own defaults apply,
    so a newly registered kind works without a row per user first.
    """
    from plinta.contrib.notifications.models import NotificationPreference

    preference = NotificationPreference.objects.filter(
        user=user, kind=subscription.name
    ).first()
    if preference is None:
        return subscription.in_app_by_default, subscription.email_by_default
    return preference.in_app, preference.email


def deliver(subscription: Subscription, obj: Any, payload: dict[str, Any]) -> int:
    """Create the rows this subscription calls for. Returns how many people
    were told, in any form."""
    from plinta.contrib.notifications.models import Notification, QueuedEmail

    if subscription.when is not None:
        try:
            if not subscription.when(obj, **payload):
                return 0
        except Exception:  # noqa: BLE001
            logger.exception("condition for %r failed", subscription.name)
            return 0

    title = resolve(subscription.title, obj, payload) or str(obj)
    body = resolve(subscription.body, obj, payload)
    url = resolve(subscription.url, obj, payload)
    content_type = ContentType.objects.get_for_model(type(obj))

    told = 0
    for person in recipients_of(subscription, obj, payload):
        in_app, by_email = wants(person, subscription)
        if in_app:
            Notification.objects.create(
                recipient=person,
                kind=subscription.name,
                title=title,
                body=body,
                url=url,
                content_type=content_type,
                object_id=getattr(obj, "pk", None),
            )
        if by_email and getattr(person, "email", ""):
            QueuedEmail.objects.create(
                to=person.email, subject=title, body=body or title,
                kind=subscription.name,
            )
        told += 1 if (in_app or by_email) else 0
    return told


def notify(obj: Any, event: str, **payload: Any) -> int:
    """Run every subscription interested in this event. Never raises.

    A notification is never worth failing somebody's write for, so a broken
    subscription is logged and the rest still run.
    """
    total = 0
    for subscription in for_event(obj, event):
        try:
            total += deliver(subscription, obj, payload)
        except Exception:  # noqa: BLE001
            logger.exception("notification %r failed", subscription.name)
    return total

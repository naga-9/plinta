"""Turning a subscription into deliveries: who hears, and on what.

Two questions, kept apart. A **subscription** decides who should be told; a
**channel** decides how they are reached. Neither knows the other's answer,
which is what lets one subscription reach one person by email and another in
the app without either being written twice.

Nothing here reaches a network. A channel that must is expected to enqueue,
because all of this runs inside the write that caused it.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from plinta.contrib.notifications import channels
from plinta.contrib.notifications.registry import Subscription, for_event

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Message:
    """What a channel is asked to deliver.

    Not a saved row: the in-app channel creates one of those, and a channel
    that posts to Discord has no use for a database row somebody must then
    mark read.
    """

    kind: str
    title: str
    body: str = ""
    url: str = ""
    target: Any = None


def resolve(value: Any, obj: Any, payload: dict[str, Any]) -> str:
    """A title, body or URL: a plain string, or a callable given the event."""
    if callable(value):
        return str(value(obj, **payload) or "")
    return str(value or "")


def recipients_of(subscription: Subscription, obj: Any, payload: dict[str, Any]) -> list:
    """Who should hear about this, with the actor removed unless asked for.

    Telling somebody what they just did is noise, and the single most common
    complaint about a notification system — so it is off unless asked for.
    """
    try:
        people = list(subscription.recipients(obj, **payload) or [])
    except Exception:  # noqa: BLE001 - a consumer's callable is not ours to trust
        logger.exception("recipients for %r failed", subscription.name)
        return []

    actor = payload.get("actor")
    if not subscription.notify_actor and actor is not None:
        people = [
            p for p in people if getattr(p, "pk", None) != getattr(actor, "pk", None)
        ]
    seen, unique = set(), []
    for person in people:
        pk = getattr(person, "pk", None)
        if pk is not None and pk not in seen:
            seen.add(pk)
            unique.append(person)
    return unique


def wants(user, subscription: Subscription, channel: channels.Channel) -> bool:
    """Whether this person wants this kind on this channel.

    Three answers, most specific first: what they said, what the subscription
    defaults to for this kind, and what the channel defaults to. So a newly
    registered kind works before anybody has a preference row, and a newly
    registered channel does not switch itself on for everyone.
    """
    from plinta.contrib.notifications.models import NotificationPreference

    stored = NotificationPreference.objects.filter(
        user=user, kind=subscription.name, channel=channel.name
    ).first()
    if stored is not None:
        return stored.enabled
    if channel.name in subscription.channels:
        return bool(subscription.channels[channel.name])
    return channel.on_by_default


def channels_for(user, subscription: Subscription) -> list[channels.Channel]:
    """The channels this person will actually be reached on.

    Wanted, and possible: somebody with no email address is not offered email,
    however enthusiastically they have opted into it.
    """
    return [
        channel
        for channel in channels.registered()
        if wants(user, subscription, channel) and channels.reachable(user, channel)
    ]


def deliver(subscription: Subscription, obj: Any, payload: dict[str, Any]) -> int:
    """Send this subscription's message. Returns how many people were reached."""
    if subscription.when is not None:
        try:
            if not subscription.when(obj, **payload):
                return 0
        except Exception:  # noqa: BLE001
            logger.exception("condition for %r failed", subscription.name)
            return 0

    message = Message(
        kind=subscription.name,
        title=resolve(subscription.title, obj, payload) or str(obj),
        body=resolve(subscription.body, obj, payload),
        url=resolve(subscription.url, obj, payload),
        target=obj,
    )

    reached = 0
    for person in recipients_of(subscription, obj, payload):
        wanted = channels_for(person, subscription)
        delivered = [
            channel
            for channel in wanted
            if channels.send(channel, person, message, subscription)
        ]
        reached += 1 if delivered else 0
    return reached


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

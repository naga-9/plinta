"""Where a notification goes.

Two ship — the in-app list and the email queue — and a third party adds a
third. A channel is registered, so Discord, Slack, SMS or a webhook is a
package that registers one rather than a change to this app.

A channel is a **name and a delivery callable**. It does not decide who hears
anything: that is the subscription's job (`registry.py`), and keeping the two
apart is what lets one subscription reach a person on whichever channels they
have asked for.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

NAME = re.compile(r"[a-z][a-z0-9_]*")


@dataclass(frozen=True)
class Channel:
    """One way of reaching somebody."""

    name: str
    label: str
    #: ``(user, notification) -> None``. Raising is logged and swallowed.
    deliver: Callable[..., None]
    #: Whether this channel can reach this person at all — no email address,
    #: no linked Discord account. A channel nobody can be reached on is not
    #: offered in their preferences.
    available: Callable[..., bool] | None = None
    #: What somebody gets before they have said. A channel that mails the
    #: world on install is a channel that gets uninstalled.
    on_by_default: bool = False


class ChannelError(Exception):
    """A channel was registered twice, or named unusably."""


_registry: dict[str, Channel] = {}


def register_channel(
    name: str,
    label: str = "",
    *,
    deliver: Callable[..., None],
    available: Callable[..., bool] | None = None,
    on_by_default: bool = False,
) -> Channel:
    """Add a way of reaching people.

        register_channel(
            "discord", "Discord",
            deliver=lambda user, notification, **kw: post_to_discord(
                user.discord_webhook, notification.title
            ),
            available=lambda user, **kw: bool(getattr(user, "discord_webhook", "")),
        )

    **Deliver without blocking.** This runs inside the write that caused the
    notification, so a channel that calls an HTTP API should enqueue rather
    than post — `email` is the worked example, and it queues.

    Raises:
        ChannelError: the name is taken, or is not lowercase
            ``[a-z][a-z0-9_]*``.
    """
    if not NAME.fullmatch(name):
        raise ChannelError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in _registry:
        raise ChannelError(f"{name!r} is already registered")
    channel = Channel(
        name=name,
        label=label or name.replace("_", " ").title(),
        deliver=deliver,
        available=available,
        on_by_default=on_by_default,
    )
    _registry[name] = channel
    return channel


def registered() -> list[Channel]:
    """Every channel, by name. What a preference screen offers."""
    return sorted(_registry.values(), key=lambda c: c.name)


def get(name: str) -> Channel | None:
    """The channel called ``name``, or None if nothing registered it."""
    return _registry.get(name)


def reachable(user, channel: Channel) -> bool:
    """Whether this person can be reached on this channel at all."""
    if channel.available is None:
        return True
    try:
        return bool(channel.available(user))
    except Exception:  # noqa: BLE001 - a consumer's probe is not ours to trust
        logger.exception("availability of %r failed", channel.name)
        return False


def send(channel: Channel, user, notification, subscription) -> bool:
    """Deliver one notification on one channel. Never raises.

    A channel that fails must not fail the others, and none of them may fail
    the write that caused the notification.
    """
    try:
        channel.deliver(user=user, notification=notification, subscription=subscription)
    except Exception:  # noqa: BLE001
        logger.exception("channel %r could not deliver", channel.name)
        return False
    return True

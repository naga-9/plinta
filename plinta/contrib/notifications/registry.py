"""What is worth telling whom.

A consumer registers a **subscription**: which model, which event, who hears
about it, and under what condition. The same registry shape everything else in
plinta uses — a module dict, a `register_*`, and a lookup.

The alternative is a table of rules edited in a browser, which would make
"who gets told" a validation surface and a place for a stored callable path.
A registration is code, reviewed like code.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

NAME = re.compile(r"[a-z][a-z0-9_]*")

#: The events a subscription may name. Each maps to a core signal (§4.1);
#: nothing here invents one.
EVENTS = frozenset({"written", "created", "updated", "deleted", "state_changed",
                    "comment_posted"})


@dataclass(frozen=True)
class Subscription:
    """One registered interest."""

    name: str
    #: ``"catalog.Sale"``, matched case-insensitively against the model label.
    model_label: str
    event: str
    #: Takes the object and the event's payload; returns users.
    recipients: Callable[..., Iterable[Any]]
    #: Whether this particular occurrence is worth telling anyone about.
    when: Callable[..., bool] | None = None
    title: str | Callable[..., str] = ""
    body: str | Callable[..., str] = ""
    url: str | Callable[..., str] = ""
    #: What a person gets before they have expressed a preference.
    in_app_by_default: bool = True
    email_by_default: bool = False
    #: Whether the person who caused it hears about it.
    notify_actor: bool = field(default=False)


class SubscriptionError(Exception):
    """A subscription was registered twice, named unusably, or names an event
    that is not in the vocabulary."""


_registry: dict[str, Subscription] = {}


def register_notification(
    name: str,
    model_label: str,
    event: str,
    *,
    recipients: Callable[..., Iterable[Any]],
    when: Callable[..., bool] | None = None,
    title: str | Callable[..., str] = "",
    body: str | Callable[..., str] = "",
    url: str | Callable[..., str] = "",
    in_app_by_default: bool = True,
    email_by_default: bool = False,
    notify_actor: bool = False,
) -> Subscription:
    """Say that something is worth telling somebody about.

        register_notification(
            "sale_recorded", "catalog.Sale", "created",
            recipients=lambda obj, **kw: obj.store.managers.all(),
            title=lambda obj, **kw: f"A sale at {obj.store}",
        )

    `title`, `body` and `url` are a plain string or a callable. **Not a format
    template** — a stored string with `{obj.owner.email}` in it is a path from
    configuration into attribute traversal, and this registry is code precisely
    so that it need not be one.

    Raises:
        SubscriptionError: the name is taken, is not lowercase
            ``[a-z][a-z0-9_]*``, or the event is not one core emits.
    """
    if not NAME.fullmatch(name):
        raise SubscriptionError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in _registry:
        raise SubscriptionError(f"{name!r} is already registered")
    if event not in EVENTS:
        known = ", ".join(sorted(EVENTS))
        raise SubscriptionError(f"{event!r} is not an event plinta emits ({known})")

    subscription = Subscription(
        name=name,
        model_label=model_label.lower(),
        event=event,
        recipients=recipients,
        when=when,
        title=title,
        body=body,
        url=url,
        in_app_by_default=in_app_by_default,
        email_by_default=email_by_default,
        notify_actor=notify_actor,
    )
    _registry[name] = subscription
    return subscription


def registered() -> dict[str, Subscription]:
    """Every subscription, by name. What a preference screen offers."""
    return dict(_registry)


def for_event(obj: Any, event: str) -> list[Subscription]:
    """The subscriptions that care about this event on this object."""
    try:
        label = f"{obj._meta.app_label}.{obj._meta.model_name}"
    except AttributeError:
        return []
    return [
        s
        for s in _registry.values()
        if s.event == event and s.model_label == label
    ]

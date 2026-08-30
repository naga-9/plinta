"""What an app contributes to the topbar.

The shell draws the chrome and knows what is in it only by asking. A bell for
an app that may not be installed cannot be core's — it would be core naming a
contrib package, which is the line §10 draws.

The same shape as the sidebar's fixed links (`links.py`): a registration with
a template, a permission and an order, and core renders whatever is there.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

NAME = re.compile(r"[a-z][a-z0-9_]*")


@dataclass(frozen=True)
class TopbarItem:
    """One thing drawn in the topbar's actions."""

    name: str
    #: Rendered with the request in context, so it can count its own rows.
    template: str
    #: ``app_label.codename``, or blank for something everyone sees.
    permission: str = ""
    order: int = 100


class TopbarError(Exception):
    """An item was registered twice, or named unusably."""


_registry: dict[str, TopbarItem] = {}


def register_topbar_item(
    name: str, *, template: str, permission: str = "", order: int = 100
) -> TopbarItem:
    """Put something in the topbar.

        register_topbar_item(
            "notifications", template="plinta/notifications/bell.html",
            permission="plinta_notifications.view_notification", order=10,
        )

    Raises:
        TopbarError: the name is taken, or is not lowercase
            ``[a-z][a-z0-9_]*``.
    """
    if not NAME.fullmatch(name):
        raise TopbarError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in _registry:
        raise TopbarError(f"{name!r} is already registered")
    item = TopbarItem(
        name=name, template=template, permission=permission, order=order
    )
    _registry[name] = item
    return item


def registered() -> list[TopbarItem]:
    """Every item, in display order."""
    return sorted(_registry.values(), key=lambda i: (i.order, i.name))


def visible_items(user: Any) -> list[TopbarItem]:
    """The items this viewer may see.

    An item with no permission is drawn for anybody signed in; one naming a
    permission is drawn only for a holder, so an app's chrome disappears with
    its access rather than showing a control that refuses.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    return [
        item
        for item in registered()
        if not item.permission or user.has_perm(item.permission)
    ]

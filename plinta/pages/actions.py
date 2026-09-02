"""What an app contributes to a page's own header.

The topbar is the shell's chrome and is the same on every screen. This is the
**page's** actions, beside its title, and an action registered here is handed
the page it is drawn on — which is the whole difference, and the reason the
topbar's registry could not serve.

It exists so the layout composer can be a contrib app (§12.4). Core stores a
placement's four integers and writes them; dragging them is an enhancement,
and an enhancement that core names by package is not one. So core draws
whatever is registered and knows nothing about GridStack.

    register_page_action(
        "compose",
        template="composer/edit_layout.html",
        permission="plinta_pages.change_pageblock",
        order=10,
    )

The same shape as `shell/topbar.py` and `shell/links.py`, deliberately: a
template, a permission and an order. What differs is the context — a page
action is rendered with `page` and `request`, so it can build a URL for the
page it sits on.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

NAME = re.compile(r"[a-z][a-z0-9_]*")


@dataclass(frozen=True)
class PageAction:
    """One control drawn in a page's header."""

    name: str
    #: Rendered with ``page`` and the request in context.
    template: str
    #: ``app_label.codename``, or blank for something everyone sees.
    permission: str = ""
    #: The page types this action suits. Empty means every type — right for
    #: an action about the page itself, wrong for one about a grid, since a
    #: `custom-template` page has no placements to arrange.
    page_types: tuple[str, ...] = ()
    order: int = 100


class PageActionError(Exception):
    """An action was registered twice, or named unusably."""


_registry: dict[str, PageAction] = {}


def register_page_action(
    name: str,
    *,
    template: str,
    permission: str = "",
    page_types: tuple[str, ...] = (),
    order: int = 100,
) -> PageAction:
    """Put a control in every page's header.

    Raises:
        PageActionError: the name is taken, or is not lowercase
            ``[a-z][a-z0-9_]*``.
    """
    if not NAME.fullmatch(name):
        raise PageActionError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in _registry:
        raise PageActionError(f"{name!r} is already registered")
    action = PageAction(
        name=name,
        template=template,
        permission=permission,
        page_types=tuple(page_types),
        order=order,
    )
    _registry[name] = action
    return action


def registered() -> list[PageAction]:
    """Every action, in display order."""
    return sorted(_registry.values(), key=lambda a: (a.order, a.name))


def visible_actions(page: Any, user: Any) -> list[PageAction]:
    """The actions this viewer may see on ``page``.

    Narrowed by permission and by page type, so an action about arranging a
    grid does not appear on a page that has no grid — which is a control that
    refuses, and a control that refuses is worse than one that is absent.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    page_type = getattr(page, "page_type", "")
    return [
        action
        for action in registered()
        if (not action.permission or user.has_perm(action.permission))
        and (not action.page_types or page_type in action.page_types)
    ]

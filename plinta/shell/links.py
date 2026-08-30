"""The sidebar's fixed links: screens that are not `Page` records.

The authoring screens — Blocks, Data Sources — are views, not compositions,
so no `Page` row governs who sees them. The shell gates them instead, by the
permission each declares.

A registry rather than a list in the template, for the same reason everything
else here is one: the shell would otherwise name screens it does not own, and
a link would survive the removal of the app behind it.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShellLink:
    """One fixed entry in the sidebar."""

    name: str
    label: str
    #: A URL name, reversed when the sidebar draws.
    url_name: str
    #: ``app_label.codename``. The link is drawn only for a holder.
    permission: str
    #: A CSS class for whatever icon set the installation uses. Core draws it
    #: and names none, so a consumer's own set works unchanged.
    icon: str = ""
    #: ``(user) -> int | str | None``. A count beside the label, for the one
    #: thing a link cannot say on its own. None or zero draws nothing, since a
    #: badge saying "0" is worse than no badge.
    badge: Callable[..., object] | None = None
    order: int = 100

    def badge_for(self, user):
        """What to draw beside the label, or None.

        Never raises into the chrome: a link whose count fails is drawn
        without one, because a broken badge must not take down the menu.
        """
        if self.badge is None:
            return None
        try:
            value = self.badge(user)
        except Exception:  # noqa: BLE001 - a consumer's callable is not ours
            logger.exception("badge for %r failed", self.name)
            return None
        return value or None


class ShellLinkError(Exception):
    """A link was registered twice."""


_registry: dict[str, ShellLink] = {}


def register_shell_link(
    name: str,
    label: str,
    *,
    url_name: str,
    permission: str,
    icon: str = "",
    badge: Callable[..., object] | None = None,
    order: int = 100,
) -> ShellLink:
    """Add a fixed link to the sidebar.

        register_shell_link(
            "blocks", "Blocks",
            url_name="plinta:block_list", permission="plinta_blocks.view_block",
        )

    Raises:
        ShellLinkError: the name is taken.
    """
    if name in _registry:
        raise ShellLinkError(f"{name!r} is already registered")
    link = ShellLink(
        name=name,
        label=label,
        url_name=url_name,
        permission=permission,
        icon=icon,
        badge=badge,
        order=order,
    )
    _registry[name] = link
    return link


def registered() -> list[ShellLink]:
    """Every fixed link, in display order."""
    return sorted(_registry.values(), key=lambda link: (link.order, link.label))


@dataclass(frozen=True)
class DrawnLink:
    """A link as the sidebar draws it, for one viewer.

    Separate from the registration because a badge is a number for *this*
    person, and a Django template cannot call a method with an argument — so
    it is resolved before the template sees it.
    """

    label: str
    url_name: str
    icon: str
    badge: object | None


def visible_links(user) -> list[DrawnLink]:
    """The fixed links this viewer may follow, with their counts resolved.

    A plain permission check, not the policy engine: these screens are not
    rows, so there is nothing for a policy to narrow.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    return [
        DrawnLink(
            label=link.label,
            url_name=link.url_name,
            icon=link.icon,
            badge=link.badge_for(user),
        )
        for link in registered()
        if user.has_perm(link.permission)
    ]

"""The sidebar's fixed links: screens that are not `Page` records.

The authoring screens — Blocks, Data Sources — are views, not compositions,
so no `Page` row governs who sees them. The shell gates them instead, by the
permission each declares.

A registry rather than a list in the template, for the same reason everything
else here is one: the shell would otherwise name screens it does not own, and
a link would survive the removal of the app behind it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShellLink:
    """One fixed entry in the sidebar."""

    name: str
    label: str
    #: A URL name, reversed when the sidebar draws.
    url_name: str
    #: ``app_label.codename``. The link is drawn only for a holder.
    permission: str
    icon: str = ""
    order: int = 100


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
        order=order,
    )
    _registry[name] = link
    return link


def registered() -> list[ShellLink]:
    """Every fixed link, in display order."""
    return sorted(_registry.values(), key=lambda link: (link.order, link.label))


def visible_links(user) -> list[ShellLink]:
    """The fixed links this viewer may follow.

    A plain permission check, not the policy engine: these screens are not
    rows, so there is nothing for a policy to narrow.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    return [link for link in registered() if user.has_perm(link.permission)]

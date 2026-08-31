"""The whole menu: pages and fixed links, in one structure.

`pages.menu` builds what the `Page` rows say; this folds the registered links
in beside them. It lives in the shell because `pages` is below `links` and may
not import it — which is also why the two were drawn separately before, one
from the database and one under a hard-coded "Manage" heading.

**Both kinds of screen answer the same question.** A link names the section and
group it belongs to, by the same names a `MenuGroup` uses, so a contrib app
shipping a view lands beside one shipping a page instead of in a bucket of its
own.

Merged by **name**, not by row, because a link has only names. A group that
holds nothing but links needs no `MenuGroup` row, and one that holds pages
takes its order from the row.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Where a group with no section sits.
TOP = ""


@dataclass
class Group:
    """One group in the menu, with whatever is in it."""

    name: str
    order: int = 0
    pages: list[Any] = field(default_factory=list)
    links: list[Any] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.pages and not self.links


@dataclass
class Section:
    """One section, or the top of the menu when ``name`` is blank."""

    name: str
    order: int = 0
    groups: list[Group] = field(default_factory=list)

    @property
    def is_top(self) -> bool:
        """Groups that sit at the top with no heading above them."""
        return not self.name


def build(user) -> list[Section]:
    """The menu for one viewer, pages and links together.

    Permission-filtered by construction on both sides: a page the viewer may
    not open never reaches here, and a link is drawn only for a holder of the
    permission it declares.
    """
    from plinta.pages.menu import build as page_menu
    from plinta.shell.links import visible_links

    sections: dict[str, Section] = {}
    groups: dict[tuple[str, str], Group] = {}

    def group_for(section_name: str, group_name: str, order: int) -> Group:
        section = sections.get(section_name)
        if section is None:
            section = sections[section_name] = Section(name=section_name, order=order)
        key = (section_name, group_name)
        group = groups.get(key)
        if group is None:
            group = groups[key] = Group(name=group_name, order=order)
            section.groups.append(group)
        return group

    for entry in page_menu(user):
        section = entry.section
        for group_entry in entry.groups:
            target = group_for(
                section.name if section else TOP,
                group_entry.group.name,
                group_entry.group.order,
            )
            target.pages.extend(group_entry.pages)
            target.order = group_entry.group.order
            if section is not None:
                sections[section.name].order = section.order

    for link in visible_links(user):
        # A link naming a group that already holds pages joins it; one naming
        # a group nothing else uses creates it, which is how an app ships a
        # view without a `MenuGroup` row.
        group_for(link.section, link.group, link.order).links.append(link)

    ordered = sorted(sections.values(), key=lambda s: (s.order, s.name))
    for section in ordered:
        section.groups.sort(key=lambda g: (g.order, g.name))
    return [section for section in ordered if any(not g.is_empty for g in section.groups)]

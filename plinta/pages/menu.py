"""The navigation, assembled from the pages a viewer may see.

Permission-filtered by construction rather than by a second configuration: a
page the viewer cannot open never appears, and a group or section holding no
such page is not drawn.

There is no `admin_only` flag. A flag acting as a permission is the defect
§5.8 removes everywhere else; visibility follows the pages inside.
"""
from __future__ import annotations

from dataclasses import dataclass

from plinta.pages.models import MenuGroup, MenuSection, Page


@dataclass(frozen=True)
class GroupEntry:
    group: MenuGroup
    pages: list[Page]


@dataclass(frozen=True)
class SectionEntry:
    section: MenuSection
    groups: list[GroupEntry]

    @property
    def pages(self) -> list[Page]:
        """Every page under this section, across its groups."""
        return [page for entry in self.groups for page in entry.pages]


def visible_pages(user):
    """The pages this viewer may open and that ask to be in the menu."""
    from plinta.permissions import allowed

    return allowed(
        user, "view", Page.objects.filter(is_active=True, show_in_menu=True)
    ).select_related("menu_group__section")


def build(user) -> list[SectionEntry]:
    """The menu for one viewer.

    A group with no visible page is dropped, and a section with no surviving
    group with it — an empty heading is worse than a missing one, since it
    advertises something the viewer cannot reach.

    A page with no group is not in the menu: a group is where a page is placed,
    so one without a placement has not been placed.
    """
    pages = list(visible_pages(user))

    by_group: dict[int, list[Page]] = {}
    for page in pages:
        if page.menu_group_id is not None:
            by_group.setdefault(page.menu_group_id, []).append(page)

    if not by_group:
        return []

    groups = (
        MenuGroup.objects.filter(pk__in=by_group)
        .select_related("section")
        .order_by("section__order", "section__name", "order", "name")
    )

    sections: dict[int, list[GroupEntry]] = {}
    section_of: dict[int, MenuSection] = {}
    for group in groups:
        section_of[group.section_id] = group.section
        sections.setdefault(group.section_id, []).append(
            GroupEntry(group=group, pages=by_group[group.pk])
        )

    return [
        SectionEntry(section=section_of[section_id], groups=entries)
        for section_id, entries in sections.items()
    ]

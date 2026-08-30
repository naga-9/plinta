"""Composing a page: which placements a viewer gets, and with what filters.

Two degradations, both normal states rather than errors: a placed block the
viewer may not see, and one whose component is not installed. Making a block
private, or uninstalling a component, must never break the page holding it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from plinta.pages.models import (
    FilterSet,
    Page,
    PageBlock,
    PageFilter,
    PageFilterPreference,
)


@dataclass(frozen=True)
class Placement:
    """One block drawn on a page, with the grid position it occupies."""

    placement: PageBlock
    html: str
    column: int
    row: int
    width: int
    height: int

    @property
    def title(self) -> str:
        """The placement's own title, or the block's name."""
        return self.placement.title or self.placement.block.name

    @property
    def is_empty(self) -> bool:
        """Whether this drew nothing — an empty slot."""
        return not self.html


def placements_for(page: Page, user, *, tab: str = "") -> list[PageBlock]:
    """The placements to draw, in order.

    Filtered by the placement's own visibility and its tab. Whether the viewer
    may see the *block* is decided when it renders, because an unviewable block
    is an empty slot rather than a missing one — the grid keeps its shape.
    """
    # The content type is joined because every block resolves its model
    # through it, which would otherwise be a query per placement.
    placements = page.placements.filter(is_visible=True).select_related(
        "block", "block__data_source", "block__data_source__content_type"
    )
    if tab:
        placements = placements.filter(tab__in=["", tab])
    return list(placements)


def controls_of(page: Page) -> list[PageFilter]:
    """The page's filter controls, read once per page instance.

    Both the default-value lookup and the keyword building need them, and a
    page is rendered once, so the second read is a round trip for nothing.
    """
    if not hasattr(page, "_plinta_controls"):
        page._plinta_controls = list(page.filters.all())
    return page._plinta_controls


def default_filters(page: Page, user) -> dict[str, Any]:
    """The filter values to start from, when the viewer sent none.

    Their remembered state first, then their own default set, then a public
    one, then each filter's own default. Every step is something someone
    marked; nothing is picked by accident.
    """
    from plinta.permissions import allowed

    if user is not None and getattr(user, "is_authenticated", False):
        remembered = PageFilterPreference.objects.filter(page=page, owner=user).first()
        if remembered and remembered.values:
            return dict(remembered.values)

        sets = allowed(user, "view", page.filter_sets.filter(is_default=True))
        chosen = (
            sets.filter(owner=user).first() or sets.filter(owner__isnull=True).first()
        )
        if chosen:
            return dict(chosen.values)

    return {
        f.field_name: f.default_value
        for f in controls_of(page)
        if f.default_value is not None
    }


def resolve_filters(values: dict[str, Any], user) -> dict[str, Any]:
    """Filter values with their placeholders resolved for this viewer.

    A token nothing registered is left as written, so it matches nothing rather
    than widening the filter it was written to narrow.
    """
    from plinta.utils.placeholders import Context, resolve_values

    return resolve_values(values or {}, Context(user=user))


def filter_kwargs(page: Page, values: dict[str, Any], user) -> dict[str, Any]:
    """The stored values as ORM keyword arguments.

    Each declared filter contributes its own lookup, so a control declared
    ``in`` filters with ``__in``. A value for a field the page does not declare
    is ignored: the bar is what the page exposes, and the query string is not.
    """
    resolved = resolve_filters(values, user)
    out: dict[str, Any] = {}
    for control in controls_of(page):
        value = resolved.get(control.field_name)
        if value is None or value == "" or value == []:
            continue
        suffix = "" if control.lookup == "exact" else f"__{control.lookup}"
        out[f"{control.field_name}{suffix}"] = value
    return out


def render_page(
    page: Page, user, *, tab: str = "", filters: dict[str, Any] | None = None
) -> list[Placement]:
    """Draw every placement on ``page`` for ``user``.

    Returns one `Placement` per slot, including the empty ones, so the grid
    keeps its shape when a block is hidden or its component is uninstalled.
    """
    from plinta.blocks.rendering import render_block

    values = default_filters(page, user) if filters is None else filters
    kwargs = filter_kwargs(page, values, user)

    drawn = []
    for placement in placements_for(page, user, tab=tab):
        html = render_block(
            placement.block,
            user,
            extra_filters={**kwargs, **resolve_filters(placement.context_filter, user)},
        )
        drawn.append(
            Placement(
                placement=placement,
                html=html,
                column=placement.column,
                row=placement.row,
                width=placement.width,
                height=placement.height,
            )
        )
    return drawn


def remember_filters(page: Page, user, values: dict[str, Any]) -> None:
    """Store what this viewer last had the bar set to.

    Stored as written, placeholders included, so a saved ``__CURRENT_QUARTER__``
    keeps meaning the current quarter rather than freezing to one.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return
    PageFilterPreference.objects.update_or_create(
        page=page, owner=user, defaults={"values": values or {}}
    )


def saved_filter_sets(page: Page, user) -> list[FilterSet]:
    """The filter sets this viewer may choose from, in name order."""
    from plinta.permissions import allowed

    return list(allowed(user, "view", page.filter_sets.all()))

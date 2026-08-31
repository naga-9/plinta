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
    Widget,
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
    #: Set when the block could not be drawn. The card shows this instead.
    error: str = ""

    @property
    def title(self) -> str:
        """The placement's own title, or the block's name."""
        return self.placement.title or self.placement.block.name

    @property
    def is_empty(self) -> bool:
        """Whether this drew nothing — an empty slot."""
        return not self.html and not self.error


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


def resolve_filters(values: dict[str, Any], user, record: Any = None) -> dict[str, Any]:
    """Filter values with their placeholders resolved for this viewer.

    A token nothing registered is left as written, so it matches nothing rather
    than widening the filter it was written to narrow.

    ``record`` is the row a detail page is about, which is what `__RECORD__`
    resolves to.
    """
    from plinta.utils.placeholders import Context, resolve_values

    return resolve_values(values or {}, Context(user=user, record=record))


#: What a yes/no control may send. A query string carries strings, and a
#: `BooleanField` accepts "True" and "1" but not "true" — which is what the
#: bar draws, and what a remembered filter therefore stores.
TRUTHY = frozenset({"true", "1", "yes", "on", "t"})
FALSEY = frozenset({"false", "0", "no", "off", "f"})


def coerce(control: PageFilter, value: Any) -> Any:
    """One control's value as the ORM wants it, or None to drop it.

    Only booleans need this. Django coerces a string to a number, a date or a
    UUID on its own, but `BooleanField.to_python` rejects anything outside
    "True"/"False"/"1"/"0" — so a control that draws `true` raises
    `ValidationError` from inside the query rather than filtering.

    A value that is neither is dropped rather than raising: it can only come
    from a hand-edited URL, and a page that 500s on a stray parameter is worse
    than one that ignores it.
    """
    if control.widget != Widget.BOOLEAN:
        return value
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in TRUTHY:
        return True
    if text in FALSEY:
        return False
    return None


def filter_kwargs(
    page: Page, values: dict[str, Any], user, record: Any = None
) -> dict[str, Any]:
    """The stored values as ORM keyword arguments.

    Each declared filter contributes its own lookup, so a control declared
    ``in`` filters with ``__in``. A value for a field the page does not declare
    is ignored: the bar is what the page exposes, and the query string is not.
    """
    resolved = resolve_filters(values, user, record)
    out: dict[str, Any] = {}
    for control in controls_of(page):
        value = coerce(control, resolved.get(control.field_name))
        if value is None or value == "" or value == []:
            continue
        suffix = "" if control.lookup == "exact" else f"__{control.lookup}"
        out[f"{control.field_name}{suffix}"] = value
    return out


def render_page(
    page: Page,
    user,
    *,
    tab: str = "",
    filters: dict[str, Any] | None = None,
    query: Any = None,
    record: Any = None,
) -> list[Placement]:
    """Draw every placement on ``page`` for ``user``.

    Returns one `Placement` per slot, including the empty ones, so the grid
    keeps its shape when a block is hidden or its component is uninstalled.

    ``record`` is the row a detail page is about. It reaches a placement
    through its ``context_filter``, where `__RECORD__` resolves to the row's
    primary key — so one placement serves every record the page shows.

    ``query`` is the request's query string, handed to each block so it can
    build its own sort and page links. Each placement's parameters are
    prefixed with its id, so two tables on one page sort independently rather
    than moving together.
    """
    from plinta.blocks.rendering import BlockRenderError, render_block

    values = default_filters(page, user) if filters is None else filters
    kwargs = filter_kwargs(page, values, user, record)

    drawn = []
    for placement in placements_for(page, user, tab=tab):
        html, error = "", ""
        try:
            html = render_block(
                placement.block,
                user,
                extra_filters={
                    **kwargs,
                    **resolve_filters(placement.context_filter, user, record),
                },
                query=query,
                param_prefix=f"b{placement.pk}_",
                page=_page_number(query, f"b{placement.pk}_"),
                sort=_sort_param(query, f"b{placement.pk}_"),
            )
        except BlockRenderError as exc:
            # The block says so in its own slot; the other seven still draw.
            error = str(exc)
        drawn.append(
            Placement(
                placement=placement,
                html=html,
                error=error,
                column=placement.column,
                row=placement.row,
                width=placement.width,
                height=placement.height,
            )
        )
    return drawn


def _page_number(query: Any, prefix: str) -> int:
    """Which page this placement is showing. Anything unusable is the first."""
    try:
        return max(1, int((query or {}).get(f"{prefix}page", 1)))
    except (TypeError, ValueError):
        return 1


def _sort_param(query: Any, prefix: str) -> str:
    """The column this placement is sorted by, ``-`` for descending."""
    return (query or {}).get(f"{prefix}sort", "") or ""


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

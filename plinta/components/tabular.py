"""Ordering and paging, for any component that draws rows.

Not part of the `Component` contract: a chart and a KPI have neither, and a
contract every component must answer but few need is a contract that lies.
These are free functions instead, so a component that pages opts in by calling
them and one that does not simply never imports this.

The reason they are not `TableComponent` methods is the feed. A table drawn on
the server and the same table drawn by a vendor both order and page, and the
two must agree about what page two holds — a row appearing on both pages, or
on neither, is the failure. One implementation, two callers, is how they
cannot drift.
"""
from __future__ import annotations

from typing import Any, Literal

from django.core.exceptions import FieldError, ValidationError
from django.core.paginator import Page, Paginator
from django.db.models import Q
from pydantic import Field

from plinta.components.base import ComponentConfig

#: How a column is searched, by what kind of value it holds. Chosen here and
#: never sent by the client: v1 took the lookup from the query string, which
#: bought a viewer `__regex` for a denial of service and
#: `author__user__password__startswith` for a search.
LOOKUPS = {"number": "exact", "date": "exact"}
DEFAULT_LOOKUP = "icontains"


class Sort(ComponentConfig):
    """One ordering, applied in the order the list gives them."""

    field: str
    direction: Literal["asc", "desc"] = "asc"


class TabularConfig(ComponentConfig):
    """What every row-drawing component is configured with.

    A base rather than a shared schema: each component still declares its own
    config with its own extras, so switching a block between two of them is
    validated at save like any other config change.
    """

    page_size: int = Field(default=50, gt=0)
    sort: list[Sort] = Field(default_factory=list)


def ordered(rows: Any, sort: list[Sort]) -> Any:
    """``rows`` in the order ``sort`` asks for, and never in none.

    Paging an unordered queryset is not merely untidy: the database may return
    rows in a different order for each LIMIT/OFFSET, so a row can appear on two
    pages and another on none.
    """
    ordering = [f"-{s.field}" if s.direction == "desc" else s.field for s in sort]
    if ordering:
        return rows.order_by(*ordering)
    return rows if rows.ordered else rows.order_by("pk")


def paged(rows: Any, size: int, number: Any = 1) -> Page:
    """One page of ``rows``, and what a pager needs to draw itself.

    Django's `Paginator`, so an out-of-range or unparseable page number lands
    on the last page rather than raising on a link someone typed.
    """
    return Paginator(rows, size).get_page(number)


def sort_asked(asked: list[str], fields: Any) -> list[Sort]:
    """The orderings a viewer asked for, dropped where they may not have them.

    A `-` prefix means descending, which is Django's own spelling and so is
    what a reader already knows. A column the viewer may not see is not a
    column they may sort by: ordering on it would leak its values through the
    row order.
    """
    permitted = {f.field_name for f in fields or []}
    out = []
    for one in asked:
        one = (one or "").strip()
        if not one:
            continue
        field = one.lstrip("-")
        if permitted and field not in permitted:
            continue
        out.append(Sort(field=field, direction="desc" if one.startswith("-") else "asc"))
    return out


def filtered(rows: Any, asked: dict[str, Any], fields: Any) -> Any:
    """``rows`` narrowed by the per-column filters a viewer typed.

    Two gates, and the first is the important one. A filter may only name a
    column **the viewer was given** — the same list the columns were drawn
    from — so a path this datasource never exposed cannot be reached by typing
    it into a query string. The second is `filterable`: a column the author
    did not open to filtering is not filtered, even though it is visible.

    A value the field cannot hold — letters in a number column — narrows to
    nothing rather than raising. The request came from a text box, so a bad
    value is a normal event, not a server error.
    """
    allowed = {
        f.field_name: f for f in fields or [] if getattr(f, "filterable", False)
    }
    for name, value in (asked or {}).items():
        field = allowed.get(name)
        if field is None or value in (None, "", []):
            continue
        lookup = LOOKUPS.get(getattr(field, "sorter", "") or "", DEFAULT_LOOKUP)
        suffix = "" if lookup == "exact" else f"__{lookup}"
        try:
            narrowed = rows.filter(Q(**{f"{name}{suffix}": value}))
            # Evaluated here, because a value the column cannot hold raises at
            # the first read and not at the call that built the query.
            narrowed.exists()
        except (ValidationError, ValueError, FieldError):
            return rows.none()
        rows = narrowed
    return rows

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

from plinta.components.base import ColumnsConfig, ComponentConfig

#: How a column is searched, by what it **holds** — never by `sorter`, which
#: says how to compare it. Read from the sort hint, every non-text column
#: compiled to `icontains`, which is not a lookup a boolean or a relation has:
#: the filter raised, was caught, and matched nothing. Filtering by region
#: emptied the table and read as "there is no data".
#:
#: Chosen here and never sent by the client: v1 took the lookup from the query
#: string, which bought a viewer `__regex` for a denial of service and
#: `author__user__password__startswith` for a search.
LOOKUPS = {
    "number": "exact",
    "boolean": "exact",
    "date": "exact",
    "datetime": "date",
    "time": "exact",
    # A relation is filtered by the pk a picker offers, on either side of the
    # count: `region=3` and `watchers=3` are both the row having that one.
    "relation": "exact",
    "relations": "exact",
}
DEFAULT_LOOKUP = "icontains"

#: What `true` means when it arrives as text. Django's own `to_python` refuses
#: a lowercase one, which is what our own controls send.
TRUE = {"true", "1", "yes", "on", "t"}
FALSE = {"false", "0", "no", "off", "f"}


class Sort(ComponentConfig):
    """One ordering, applied in the order the list gives them."""

    field: str
    direction: Literal["asc", "desc"] = "asc"


class TabularConfig(ColumnsConfig):
    """What every row-drawing component is configured with.

    A base rather than a shared schema: each component still declares its own
    config with its own extras, so switching a block between two of them is
    validated at save like any other config change.
    """

    page_size: int = Field(
        default=50, gt=0, title="Rows per page",
    )
    sort: list[Sort] = Field(
        default_factory=list,
        title="Sort by",
        description="Ties are broken by the next row down.",
    )


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


def as_boolean(value: Any) -> Any:
    """``value`` as a boolean, or unchanged where it says neither."""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in TRUE:
        return True
    if text in FALSE:
        return False
    return value


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
    from plinta.datasources.kinds import MULTIPLE, kind_of

    allowed = {
        f.field_name: f for f in fields or [] if getattr(f, "filterable", False)
    }
    for name, value in (asked or {}).items():
        field = allowed.get(name)
        if field is None or value in (None, "", []):
            continue
        kind = kind_of(rows.model, name, getattr(field, "sorter", "") or "string")
        lookup = LOOKUPS.get(kind, DEFAULT_LOOKUP)
        if kind == "boolean":
            value = as_boolean(value)
        suffix = "" if lookup == "exact" else f"__{lookup}"
        try:
            narrowed = rows.filter(Q(**{f"{name}{suffix}": value}))
            if kind in MULTIPLE:
                # The join multiplies the rows, so without this a record with
                # two watchers appears twice on the page and the count says
                # there are more of them than there are.
                narrowed = narrowed.distinct()
            # Evaluated here, because a value the column cannot hold raises at
            # the first read and not at the call that built the query.
            narrowed.exists()
        except (ValidationError, ValueError, FieldError):
            return rows.none()
        rows = narrowed
    return rows

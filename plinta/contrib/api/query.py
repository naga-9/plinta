"""Turning query parameters into a narrowed queryset.

**No access decision happens here.** The rows arrive already narrowed by
`get_queryset` and the fields by `get_available_fields`, so everything below
can only ever narrow further. That is the property that makes the API
structurally incapable of returning what the UI would hide (§15.1) — this
module cannot widen anything even if it is wrong.

The lookup for a column comes from what the column **holds**, never from the
caller. v1 took it from the query string and validated only the head of the
traversal, so `author__user__password__startswith` was a search box and
`__regex` was a denial of service (§8.7).
"""
from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet

from plinta.components.tabular import DEFAULT_LOOKUP, LOOKUPS, as_boolean
from plinta.datasources.kinds import MULTIPLE, kind_of

#: Query parameters the API owns. Anything else naming a visible column is a
#: filter; anything else at all is ignored, because a caller misspelling a
#: field should get every row rather than a 400 nobody can act on.
RESERVED = {"page", "size", "order", "search"}

#: The most rows one response may carry. Permissions decide what a caller may
#: read; this decides how fast — browsing and bulk extraction differ in
#: economics, not in authorisation (§15.1).
MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50


def filtered(rows: QuerySet, params: dict[str, Any], fields, model) -> QuerySet:
    """``rows`` narrowed by whichever parameters name a visible column."""
    by_name = {field.field_name: field for field in fields}
    for name, value in params.items():
        if name in RESERVED or name not in by_name or value in (None, ""):
            continue
        kind = kind_of(model, name, getattr(by_name[name], "sorter", "") or "string")
        lookup = LOOKUPS.get(kind, DEFAULT_LOOKUP)
        if kind == "boolean":
            value = as_boolean(value)
            if value is None:
                continue
        rows = rows.filter(Q(**{f"{name}__{lookup}": value}))
        if kind in MULTIPLE:
            # The join multiplies rows, so a page would show a record twice
            # and the count would disagree with the page.
            rows = rows.distinct()
    return rows


def ordered(rows: QuerySet, order: str, fields) -> QuerySet:
    """``rows`` sorted by ``order``: comma-separated, `-` for descending.

    A column the caller may not see is dropped rather than refused. Ordering
    by an invisible column reveals its values through the sequence of the
    rows, which is a slower way of reading it but a way of reading it.
    """
    if not order:
        return rows
    visible = {field.field_name for field in fields}
    terms = []
    for term in order.split(","):
        term = term.strip()
        name = term[1:] if term.startswith("-") else term
        if name in visible:
            terms.append(term)
    return rows.order_by(*terms) if terms else rows


def searched(rows: QuerySet, term: str, datasource, user) -> QuerySet:
    """``rows`` narrowed to those matching ``term`` in a searchable column."""
    from plinta.datasources.services import search_q

    if not term:
        return rows
    condition = search_q(datasource, user, term)
    return rows.filter(condition) if condition is not None else rows


def page_of(rows: QuerySet, page: int, size: int) -> tuple[list, dict]:
    """One page of ``rows``, and what a caller needs to ask for the next.

    The count is taken before slicing, so `total` describes the filtered set
    rather than the page — which is what a caller paginating needs and what a
    caller checking a filter worked is actually asking.
    """
    size = max(1, min(size or DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE))
    page = max(1, page or 1)
    total = rows.count()
    start = (page - 1) * size
    return list(rows[start : start + size]), {
        "page": page,
        "size": size,
        "total": total,
        "pages": (total + size - 1) // size if size else 0,
    }

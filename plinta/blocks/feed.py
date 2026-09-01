"""The rows a fetching widget asks for, as JSON.

Private transport (§15.4): plinta's own front end talking to plinta. Not the
public API, and not because block config is editable — `DataSourceField` rows
are edited in a browser too and the public API is generated from them. It is
that **this shape depends on who is asking**: a saved view is a per-viewer
delta over the block's config, so two people requesting the same URL get
different columns. No versioned contract can promise that.

Vendor-neutral on the wire. v1's endpoint returned ``data`` and ``last_page``,
which are Tabulator's own parameter names, so every other adapter worked
around a shape named after one library.
"""
from __future__ import annotations

from typing import Any

#: What a request may ask for beyond the column filters.
RESERVED = {"page", "size", "sort", "tab", "view"}

#: Per-column filters arrive namespaced, so they cannot collide with the above
#: or be mistaken for the page's own filter bar.
COLUMN_PREFIX = "f."

#: A column's sorter says what kind of value it holds, which is what an adapter
#: needs to pick a comparator and an alignment.
NUMERIC = {"number"}


def requested(query) -> dict[str, Any]:
    """What the client asked for: paging, ordering and column filters."""
    def one(name, default=""):
        try:
            return query.get(name, default) or default
        except AttributeError:
            return default

    filters = {}
    for key in getattr(query, "keys", list)():
        if key.startswith(COLUMN_PREFIX):
            value = query.get(key)
            if value not in (None, ""):
                filters[key[len(COLUMN_PREFIX):]] = value

    return {
        "page": _int(one("page"), 1),
        "size": _int(one("size"), 0),
        "sort": [s for s in one("sort").split(",") if s],
        "filters": filters,
        "view": one("view"),
    }


def _int(value: Any, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return number if number > 0 else fallback


def column(field: Any) -> dict[str, Any]:
    """One column, as an adapter needs to draw its header.

    `sortable` and `filterable` are what let an adapter draw the right
    control: a filter box on a column that cannot be filtered is a control
    that does nothing, and a sorter needs to know whether it is comparing text
    or numbers.
    """
    kind = getattr(field, "sorter", "") or "string"
    return {
        "name": field.field_name,
        "label": field.label,
        "type": kind,
        "align": "right" if kind in NUMERIC else "left",
        "sortable": True,
        "filterable": bool(getattr(field, "filterable", False)),
        "wrap": getattr(field, "format", "") == "textarea",
        "width": getattr(field, "width", None),
    }


def cell(row: Any, field: Any, user) -> Any:
    """One value, formatted the way every other output formats it.

    Text, or **markup** where the column declares a field renderer — a chip, a
    link, a progress bar. An adapter that draws it as HTML gets the same cell
    a server-rendered table would; one that cannot simply shows the markup,
    which is why a renderer is a column's declaration and not a default.
    """
    from plinta.renderers.html import cell as rendered

    return str(rendered(row, field, user))


def feed(component, config, user, *, datasource, narrow, asked) -> dict[str, Any]:
    """Rows, columns and paging for one block, as the client wants them.

    Ordering and paging are the component's own — the same methods a
    server-rendered table uses — so a fetching table and an inline one cannot
    disagree about what page two is.
    """
    rows, fields = component.get_data(
        config, user, datasource=datasource, narrow=narrow
    )

    # The sort is honoured after the columns are known, because which columns
    # the viewer may see is what decides which may be sorted on.
    config = component.requested_sort(
        config, {"sort": ",".join(asked["sort"]), "fields": fields}
    )
    rows = component.ordered(rows, config)

    size = asked["size"] or getattr(config, "page_size", 50)
    page = component.page(rows, config.model_copy(update={"page_size": size}),
                          asked["page"])

    return {
        "columns": [column(f) for f in fields],
        "rows": [
            {f.field_name: cell(row, f, user) for f in fields}
            for row in page.object_list
        ],
        "page": {
            "number": page.number,
            "count": page.paginator.num_pages,
            "total": page.paginator.count,
            "size": size,
        },
        # What was **applied**, never what was asked. A sort on a column the
        # viewer may not see is dropped silently, and a client drawing its own
        # request would show an arrow on a column that is not sorted.
        "applied": {
            "sort": [
                f"-{s.field}" if s.direction == "desc" else s.field
                for s in config.sort
            ],
            "filters": asked["filters"],
        },
    }

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

import datetime
import decimal
from typing import Any

from plinta.components.tabular import filtered, ordered, paged, sort_asked
from plinta.datasources.choices import THRESHOLD, choosable as choices

#: What a request may ask for beyond the column filters.
RESERVED = {"page", "size", "sort", "tab", "view"}

#: Per-column filters arrive namespaced, so they cannot collide with the above
#: or be mistaken for the page's own filter bar.
COLUMN_PREFIX = "f."

#: A column's sorter says what kind of value it holds, which is what an adapter
#: needs to pick a comparator and an alignment.
NUMERIC = {"number"}

#: A row carries its own identity under this key, because a write names the
#: row it is writing. Underscored so it cannot collide with a column: a field
#: path names a model field, and a leading underscore is not one anybody has.
RECORD = "_record"

#: And its **unformatted** values, for the columns it may edit.
#:
#: A cell is formatted for reading — `No`, `£8.75`, a chip — and none of those
#: can be edited: an editor seeded with `£8.75` sends `£8.75` back, and one
#: seeded with `No` sends the word. So an editable column travels twice, once
#: to read and once to change.
EDIT = "_edit"

#: What a column *holds*, which is not what `sorter` answers. `sorter` says
#: how to compare a column; this says what kind of value it is, which is what
#: decides an editor. They agree for text and numbers and part company at
#: booleans, dates and relations — the three that need an editor that is not
#: a text box.
KINDS = {
    "AutoField": "number",
    "BigAutoField": "number",
    "BigIntegerField": "number",
    "BooleanField": "boolean",
    "DateField": "date",
    "DateTimeField": "datetime",
    "DecimalField": "number",
    "FloatField": "number",
    "IntegerField": "number",
    "PositiveIntegerField": "number",
    "PositiveSmallIntegerField": "number",
    "SmallIntegerField": "number",
    "TimeField": "time",
}


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


def kind_of(model, path: str, fallback: str) -> str:
    """What the column at ``path`` holds.

    ``fallback`` is the sort hint, used where the path resolves to no model
    field — an annotation, a property, a reverse accessor. Those are readable
    and never editable, so a sort hint is all they need.
    """
    from plinta.datasources.services import resolve_path

    field = resolve_path(model, path)
    if field is None:
        return fallback
    if getattr(field, "many_to_one", False) or getattr(field, "one_to_one", False):
        return "relation"
    if getattr(field, "many_to_many", False):
        return "relations"
    return KINDS.get(type(field).__name__, "string")


def raw(row: Any, name: str, kind: str) -> Any:
    """One value as the field holds it, ready to seed an editor.

    JSON has no date and no Decimal, so both are sent in a form the browser
    can read back and the server can parse: a relation as the pk it is
    written by, a date as ISO-8601.
    """
    if kind == "relation":
        return getattr(row, f"{name}_id", None)
    value = getattr(row, name, None)
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    return value


def row_payload(row: Any, fields: list, user, editable: set[str],
                kinds: dict[str, str]) -> dict[str, Any]:
    """One row, as both halves of the conversation send it.

    The feed sends a page of these and a write answers with one, so a widget
    refreshes an edited row with exactly what it drew it from.
    """
    payload: dict[str, Any] = {RECORD: row.pk}
    payload.update({f.field_name: cell(row, f, user) for f in fields})
    if editable:
        payload[EDIT] = {
            f.field_name: raw(row, f.field_name, kinds.get(f.field_name, "string"))
            for f in fields
            if f.field_name in editable
        }
    return payload


def picker(field: Any, model, user) -> dict[str, Any]:
    """How an editable relation offers its choices, and the small ones inline.

    A list is by definition short — under a hundred, or the author said so —
    so it travels with the column and costs no round trip. A search cannot,
    and asks the options endpoint as the writer types.
    """
    from plinta.datasources.choices import mode_for, options

    rows = choices(model, field.field_name, user)
    if rows is None:
        return {}
    mode = mode_for(field, rows)
    drawn: dict[str, Any] = {"picker": mode}
    if mode == "list":
        drawn["options"] = options(rows, limit=THRESHOLD)
    return drawn


def column(field: Any, *, editable: bool = False, kind: str = "") -> dict[str, Any]:
    """One column, as an adapter needs to draw its header.

    `sortable`, `filterable` and `editable` are what let an adapter draw the
    right control: a filter box on a column that cannot be filtered is a
    control that does nothing, an editor on one that cannot be written is a
    promise the server will break, and a sorter needs to know whether it is
    comparing text or numbers.

    ``editable`` is per **viewer**, not per column — two people opening the
    same card get different answers — so it is passed in rather than read off
    the field.
    """
    kind = kind or getattr(field, "sorter", "") or "string"
    return {
        "name": field.field_name,
        "label": field.label,
        "type": kind,
        "align": "right" if kind in NUMERIC else "left",
        "sortable": True,
        "filterable": bool(getattr(field, "filterable", False)),
        # Which control the header draws, when the widget draws one at all.
        # Blank means the column offers no box of its own.
        "filter": getattr(field, "header_filter", "") or "",
        "editable": editable,
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

    Ordering and paging come from `components.tabular`, which is also what a
    server-rendered table uses — so a fetching table and an inline one cannot
    disagree about what page two holds.
    """
    rows, fields = component.get_data(
        config, user, datasource=datasource, narrow=narrow
    )

    # Only asked when the component can act on the answer: working out what
    # this viewer may write costs a permission read, and a chart would pay it
    # to be told about editors it will never draw.
    if getattr(component, "writes", False):
        from plinta.blocks.submit import writable

        editable = set(writable(datasource, user))
    else:
        editable = set()

    kinds = {
        f.field_name: kind_of(
            datasource.model, f.field_name, getattr(f, "sorter", "") or "string"
        )
        for f in fields
    }

    # The sort is honoured after the columns are known, because which columns
    # the viewer may see is what decides which may be sorted on. Nothing asked
    # for leaves the block's own ordering in place.
    sort = sort_asked(asked["sort"], fields) or list(getattr(config, "sort", []))
    rows = ordered(filtered(rows, asked["filters"], fields), sort)

    size = asked["size"] or getattr(config, "page_size", 50)
    page = paged(rows, size, asked["page"])

    return {
        "columns": [
            column(
                f,
                editable=f.field_name in editable,
                kind=kinds.get(f.field_name, ""),
            )
            # A picker only where the viewer may actually write the column:
            # offering choices for one they cannot change is a control that
            # does nothing, and it costs a query to build.
            | (
                picker(f, datasource.model, user)
                if f.field_name in editable and kinds.get(f.field_name) == "relation"
                else {}
            )
            for f in fields
        ],
        "rows": [
            row_payload(row, fields, user, editable, kinds)
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
                f"-{s.field}" if s.direction == "desc" else s.field for s in sort
            ],
            "filters": {
                name: value
                for name, value in asked["filters"].items()
                if name in {f.field_name for f in fields if f.filterable}
            },
        },
    }

"""The write a widget submits, applied through the pipeline.

`feed` is the read half of one card's conversation with the server; this is
the write half. Both are placement-scoped and neither knows what a widget is.

**One shape for every component that writes** (§8.11). A row and the fields
being written is what a dragged kanban card is, what an edited table cell is,
and what a submitted form is. A per-component endpoint would make three shapes
for one operation, and the first would be table-shaped because the table is
what gets built first.

Nothing here decides whether a write is allowed. `write.authorise` does that —
both permission tiers and then each field — and this adds the one gate the
pipeline cannot know about: whether the DataSource offered the column for
editing at all.
"""
from __future__ import annotations

from typing import Any

from plinta.blocks.write import WriteDenied, write_or_errors

#: A path through a relation names a column on another row. Reading one is
#: ordinary; writing one would mean deciding which row it meant, so a
#: traversal is never writable however it is declared.
TRAVERSAL = "__"


def submitted(body: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """The record and the values out of a request body.

    A body with no record is a create, which is why the two are separated
    here rather than left for each caller to agree on.
    """
    record = body.get("record")
    values = body.get("values")
    return (record if record not in ("", None) else None,
            values if isinstance(values, dict) else {})


def writable(datasource, user) -> dict[str, Any]:
    """The columns this viewer may write, by name.

    Three things at once, and each is a separate decision by a different
    person: the DataSource author declared the column `editable`, an
    administrator granted this viewer its change permission, and neither of
    them can make a traversal writable.
    """
    from plinta.datasources.services import editable_fields

    return {
        field.field_name: field
        for field in editable_fields(datasource, user)
        if TRAVERSAL not in field.field_name
    }


def submit(
    block,
    user,
    *,
    datasource,
    record: Any = None,
    values: dict[str, Any],
    narrow=None,
) -> dict[str, Any]:
    """Apply ``values`` to ``record``, or create a row when there is none.

    Returns ``{"record", "values", "errors"}``. ``values`` is the saved row
    read back, because a write can change a column the database derived and
    the widget that sent it has to redraw something.

    Raises:
        WriteDenied: the column is not one this viewer may write, or the row
            is not one they may reach. A 403 at the endpoint.
    """
    from plinta.blocks.feed import cell
    from plinta.datasources.services import get_available_fields, get_queryset

    allowed = writable(datasource, user)
    refused = sorted(set(values) - set(allowed))
    if refused:
        # Refused, never dropped. Saving the rest and reporting success would
        # tell the caller a write happened that did not — the same rule the
        # pipeline applies to a field permission.
        raise WriteDenied(
            f"not writable here: {', '.join(refused)}", denied_fields=refused
        )

    model = datasource.model
    if record is None:
        instance = model()
    else:
        # From the rows this viewer may see, narrowed the way the block is:
        # a card scoped to one region may not write outside it, and a row
        # they cannot read is one they cannot write.
        rows = get_queryset(datasource, user, columns=[])
        if narrow is not None:
            rows = narrow(rows)
        instance = rows.filter(pk=record).first()
        if instance is None:
            raise WriteDenied("no such record here")

    saved, errors = write_or_errors(
        instance, values, user, source=f"block:{block.name}"
    )
    if errors is not None:
        return {"record": record, "values": {}, "errors": errors}

    fields = get_available_fields(datasource, user)
    return {
        "record": saved.pk,
        "values": {f.field_name: cell(saved, f, user) for f in fields},
        "errors": None,
    }

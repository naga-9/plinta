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


def coerced(datasource, values: dict[str, Any]) -> dict[str, Any]:
    """``values`` as the model wants them.

    One conversion, and it is the relations: a write names a related row by
    its **pk**, because that is what a picker has and what survives JSON. The
    row is fetched here so a pk that names nothing is a rejection with a
    field on it rather than an integrity error from the database.

    Which related rows may be chosen is not settled here — a picker offering
    only permitted options, and this validating against the same list, is
    `editor_queryset_filter`'s job and is still to come.

    Raises:
        ValidationError: a relation value that names no row.
    """
    from django.core.exceptions import ValidationError

    from plinta.datasources.services import resolve_path

    model = datasource.model
    out: dict[str, Any] = {}
    for name, value in values.items():
        field = resolve_path(model, name)
        relation = field is not None and (
            getattr(field, "many_to_one", False)
            or getattr(field, "one_to_one", False)
        )
        if not relation or value in (None, ""):
            out[name] = value
            continue
        try:
            row = field.related_model._default_manager.filter(pk=value).first()
        except (ValueError, TypeError):
            # A pk the key cannot even be compared against — a label typed
            # into a box that wanted an option. The lookup raises rather than
            # matching nothing, so it is caught here and not at the database.
            row = None
        if row is None:
            raise ValidationError({name: ["Select a valid option."]})
        out[name] = row
    return out


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

    Returns ``{"record", "row", "errors"}``. ``row`` is the saved record read
    back in the same shape a feed row has, because a write can change a column
    the database derived and the widget that sent it has to redraw something.

    Raises:
        WriteDenied: the column is not one this viewer may write, or the row
            is not one they may reach. A 403 at the endpoint.
    """
    from django.core.exceptions import ValidationError

    from plinta.blocks.feed import kind_of, row_payload
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

    try:
        prepared = coerced(datasource, values)
    except ValidationError as exc:
        return {"record": record, "row": None, "errors": exc.message_dict}

    saved, errors = write_or_errors(
        instance, prepared, user, source=f"block:{block.name}"
    )
    if errors is not None:
        return {"record": record, "row": None, "errors": errors}

    fields = get_available_fields(datasource, user)
    kinds = {
        f.field_name: kind_of(
            datasource.model, f.field_name, getattr(f, "sorter", "") or "string"
        )
        for f in fields
    }
    return {
        "record": saved.pk,
        # The same shape the feed sends, so a widget refreshes an edited row
        # with exactly what it drew it from.
        "row": row_payload(saved, fields, user, set(allowed), kinds),
        "errors": None,
    }

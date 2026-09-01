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


def coerced(datasource, values: dict[str, Any], user) -> dict[str, Any]:
    """``values`` as the model wants them.

    One conversion, and it is the relations: a write names a related row by
    its **pk**, because that is what a picker has and what survives JSON.

    Resolved through the **same list the picker offers**, so a pk that was
    never on offer is refused. Fetching by pk alone would let a viewer assign
    a related row they cannot see by typing its number, which is the failure
    `editor_queryset_filter` had — it narrowed the dropdown and not the save.

    Raises:
        ValidationError: a relation value naming no row this viewer may pick.
    """
    from plinta.datasources.choices import choosable, is_multiple

    model = datasource.model
    out: dict[str, Any] = {}
    for name, value in values.items():
        rows = choosable(model, name, user)
        if rows is None or value in (None, ""):
            out[name] = value
            continue
        if is_multiple(model, name):
            out[name] = _many(rows, name, value)
        else:
            out[name] = _one(rows, name, value)
    return out


def _one(rows, name: str, value: Any):
    """The single row ``value`` names, from what may be chosen."""
    from django.core.exceptions import ValidationError

    try:
        row = rows.filter(pk=value).first()
    except (ValueError, TypeError):
        # A pk the key cannot even be compared against — a label typed into a
        # box that wanted an option. The lookup raises rather than matching
        # nothing, so it is caught here and not at the database.
        row = None
    if row is None:
        raise ValidationError({name: ["Select a valid option."]})
    return row


def _many(rows, name: str, value: Any):
    """Every row ``value`` names — and an empty list clears the column.

    All of them must be choosable, not merely some: taking the ones that
    happened to be permitted would report a success for a write nobody asked
    for, which is the same reason a denied field is refused and not dropped.
    """
    from django.core.exceptions import ValidationError

    if not isinstance(value, (list, tuple)):
        raise ValidationError({name: ["Select one or more options."]})
    if not value:
        return []
    try:
        found = list(rows.filter(pk__in=value))
    except (ValueError, TypeError):
        found = []
    if len(found) != len({str(pk) for pk in value}):
        raise ValidationError({name: ["Select valid options."]})
    return found


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
        prepared = coerced(datasource, values, user)
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

"""What a filter control offers to choose from.

**The values actually present in the rows the viewer can see** — not every row
of the related table. A filter offers what would match something, so a viewer
with no sales is offered no stores, and one whose sales are all at Hale Street
is offered Hale Street.

The permission scoping comes with that rather than being added to it: the rows
are already narrowed by both tiers, so a value can only appear if a row
carrying it is visible. v1's equivalent took no user and queried the target
table, listing every branch by name to somebody who could see two stores'
rows.

**And each control is narrowed by the others.** Choosing a store leaves the
book filter offering only books sold at it. A control never narrows *itself*,
or picking one option would remove the alternatives from its own list and the
choice could not be changed.
"""
from __future__ import annotations

from typing import Any

#: More than this and a native `<select>` is the wrong control — the page
#: carries every option. Not a refusal: the list is capped, the widget says so,
#: and a widget that fetches its options has no such limit.
CAP = 500


def options_for(
    control: Any, user, *, siblings: dict[str, Any] | None = None, limit: int = CAP
) -> list[tuple[str, str]]:
    """``[(value, label)]`` for one control, as its widget should draw them.

    Args:
        control: the `PageFilter`.
        user: the viewer. Their rows are what the options come from.
        siblings: ORM keyword arguments from the *other* controls, already
            resolved. This control's own selection must not be among them.
        limit: how many to return.

    Returns nothing when the control names no DataSource, or when its model is
    not installed — and its widget then falls back to a text input.
    """
    source = getattr(control, "data_source", None)
    if source is None:
        return []

    model = source.content_type.model_class()
    if model is None:
        return []

    from plinta.permissions import allowed

    rows = allowed(user, "view", model._default_manager.all())
    if siblings:
        rows = rows.filter(**siblings)

    path = control.field_name
    values = list(
        rows.exclude(**{f"{path}__isnull": True})
        # `order_by()` clears any Meta ordering first. Left in place, its
        # columns join the SELECT and DISTINCT then applies across them, so
        # the same store comes back once per sale.
        .order_by()
        .values_list(path, flat=True)
        .distinct()[:limit]
    )
    return label(model, path, values)


def label(model, path: str, values: list) -> list[tuple[str, str]]:
    """Pair each raw value with what a person should read.

    Three cases, and none needs configuration:

    - a field with `choices` shows its display, not its stored code
    - a relation shows `str(obj)`, which is what Django's own model choice
      field does
    - anything else is its own label
    """
    from plinta.datasources.services import resolve_path

    field = resolve_path(model, path)

    if field is not None and getattr(field, "choices", None):
        display = dict(field.choices)
        pairs = [(str(v), str(display.get(v, v))) for v in values]
    elif field is not None and getattr(field, "related_model", None) is not None:
        # One bounded query for the labels. The rows carrying these values are
        # already visible to the viewer, so the value is not new to them —
        # only its display is.
        related = field.related_model
        by_pk = related._default_manager.in_bulk(values)
        pairs = [(str(v), str(by_pk[v])) for v in values if v in by_pk]
    else:
        pairs = [(str(v), str(v)) for v in values]

    # Sorted by what is read, not by what is stored: ordering foreign keys by
    # primary key puts a list of names in insertion order, which reads as no
    # order at all.
    return sorted(pairs, key=lambda pair: pair[1].lower())


def truncated(options: list, limit: int = CAP) -> bool:
    """Whether the list hit the cap, so a control can say so."""
    return len(options) >= limit

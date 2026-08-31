"""What a filter control offers to choose from.

**Scoped to the viewer.** v1's equivalent took no user and listed every row of
the related table, so a store filter showed all store names to somebody who
could see two stores' rows: the rows were protected and the option list was
not. A dropdown that names rows you may not see is a leak whatever draws it.

Two sources, in order:

1. the model field's own `choices` — a finite, hand-written set
2. an FK's target rows, narrowed by the viewer's policy on that model

Anything else offers nothing, and its control falls back to a text input.
"""
from __future__ import annotations

from typing import Any

#: More than this and a native `<select>` is the wrong control — the page
#: carries every option. Not a refusal: the list is capped and the widget says
#: so, and a widget that fetches its options (contrib) has no such limit.
CAP = 500


def options_for(control: Any, user, *, limit: int = CAP) -> list[tuple[str, str]]:
    """``[(value, label)]`` for one control, as its widget should draw them.

    Returns nothing when the control names no DataSource, when the path is not
    a model field, or when the field is neither a choice list nor a relation.
    """
    source = getattr(control, "data_source", None)
    if source is None:
        return []

    from plinta.datasources.services import resolve_path

    model = source.content_type.model_class()
    if model is None:
        return []

    field = resolve_path(model, control.field_name)
    if field is None:
        return []

    if getattr(field, "choices", None):
        return [(str(value), str(label)) for value, label in field.choices]

    related = getattr(field, "related_model", None)
    if related is None:
        return []
    return _rows(related, user, limit)


def _rows(model, user, limit: int) -> list[tuple[str, str]]:
    """The related rows this viewer may see, as options.

    `allowed` applies both tiers, so a viewer without the model permission
    gets an empty list rather than every row — which reads as "nothing to
    choose" and is the truth.
    """
    from plinta.permissions import allowed

    rows = allowed(user, "view", model._default_manager.all())
    return [(str(row.pk), str(row)) for row in rows[:limit]]


def truncated(options: list, limit: int = CAP) -> bool:
    """Whether the list hit the cap, so a control can say so."""
    return len(options) >= limit

"""What a relation column may be set to.

One list, two readers: the picker offers it and the write validates against
it. Two lists would mean a dropdown that constrains and a save that does not,
which is why `editor_queryset_filter` was dropped (§6.2) — it narrowed three
read paths and no write.

The narrowing needs no configuration: the choosable rows are the rows the
viewer may **view**, which is the same question `datasources` answers for
every other queryset. A related row somebody cannot see is not one they can
be asked to choose, and not one they may assign.
"""
from __future__ import annotations

from functools import reduce
from operator import or_
from typing import Any

from django.db.models import Q

from plinta.datasources.services import TEXT_FIELDS, resolve_path

#: Where `auto` stops offering a list and starts offering a search (§6.2).
THRESHOLD = 100

#: What a search answers with at most. A picker is for choosing, not reading.
LIMIT = 50


def related_field(model, path: str):
    """The relation at ``path``, or None where it is not one."""
    field = resolve_path(model, path)
    if field is None:
        return None
    if getattr(field, "many_to_one", False) or getattr(field, "one_to_one", False):
        return field
    return None


def choosable(model, path: str, user):
    """The rows this viewer may set ``path`` to, or None.

    None where the column is not a relation at all, which a caller reads as
    "there is nothing to pick from" rather than "pick from nothing".
    """
    from plinta.permissions import allowed

    field = related_field(model, path)
    if field is None:
        return None
    return allowed(user, "view", field.related_model._default_manager.all())


def searched(rows, term: str):
    """``rows`` matching ``term`` across the model's own text columns.

    Its own, and not a traversal: a picker searches what its labels are made
    of. No configuration, because a model that needs a different search has
    a `__str__` that says so and a manager that can be given one later.
    """
    term = (term or "").strip()
    if not term:
        return rows
    names = [
        f.name
        for f in rows.model._meta.get_fields()
        if isinstance(f, TEXT_FIELDS) and not getattr(f, "choices", None)
    ]
    if not names:
        return rows
    return rows.filter(
        reduce(or_, (Q(**{f"{name}__icontains": term}) for name in names))
    )


def mode_for(field: Any, rows) -> str:
    """`list` or `search`, resolving `auto` against how many there are.

    A hundred rows is where a list stops being a list and starts being a
    scroll, and the author may say so themselves instead.
    """
    asked = getattr(field, "picker_mode", "auto") or "auto"
    if asked in ("list", "search"):
        return asked
    return "list" if rows.count() <= THRESHOLD else "search"


def options(rows, *, search: str = "", limit: int = LIMIT) -> list[dict[str, Any]]:
    """``[{"value": pk, "label": str(row)}]``, as a picker draws them.

    `str(row)` and nothing configurable, the same label Django's own
    `ModelChoiceField` uses — so a model already reading well in the admin
    reads well here without being told twice.
    """
    return [
        {"value": row.pk, "label": str(row)}
        for row in searched(rows, search).order_by("pk")[:limit]
    ]

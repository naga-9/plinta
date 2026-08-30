"""Deriving the joins a set of columns needs.

Both inputs belong to this layer — the columns come from ``DataSourceField``,
the queryset from ``get_queryset`` — so the derivation does too. A component
contributes nothing to the decision, and one written tomorrow gets this without
knowing it exists.
"""
from __future__ import annotations

from collections.abc import Iterable

from django.db.models import QuerySet


def derive(model, paths: Iterable[str]) -> tuple[set[str], set[str]]:
    """The ``select_related`` and ``prefetch_related`` a column set needs.

    A path reaching a forward relation joins; one starting at a reverse
    accessor or a many-to-many prefetches, since neither can be joined into a
    single row.

    A path that does not resolve is skipped: a property, an annotation or a
    reverse accessor named directly are all legitimate columns, and none of
    them is something to join.
    """
    select: set[str] = set()
    prefetch: set[str] = set()

    for path in paths:
        parts = path.split("__")
        first = _field(model, parts[0])

        if first is not None and (first.many_to_many or first.one_to_many):
            prefetch.add(parts[0])
            continue

        # Walk while the segments keep resolving to forward relations, and join
        # as far as they do. `region__name` joins `region`; `region` alone joins
        # itself, because rendering it reads the related object.
        current, reached = model, []
        for part in parts:
            field = _field(current, part)
            if field is None or not field.is_relation or field.related_model is None:
                break
            if field.many_to_many or field.one_to_many:
                break
            reached.append(part)
            current = field.related_model
        if reached:
            select.add("__".join(reached))

    return select, prefetch


def _field(model, name):
    try:
        return model._meta.get_field(name)
    except Exception:
        return None


def apply(
    queryset: QuerySet,
    paths: Iterable[str],
    *,
    extra_select: Iterable[str] = (),
    extra_prefetch: Iterable[str] = (),
) -> QuerySet:
    """Apply the derived joins to ``queryset``.

    The extras are for a renderer that reads a relation no column names — it
    declares that at registration rather than the derivation guessing.
    """
    select, prefetch = derive(queryset.model, paths)
    select |= set(extra_select)
    prefetch |= set(extra_prefetch)
    if select:
        queryset = queryset.select_related(*sorted(select))
    if prefetch:
        queryset = queryset.prefetch_related(*sorted(prefetch))
    return queryset

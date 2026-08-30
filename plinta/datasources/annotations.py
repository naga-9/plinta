"""Computed columns: registered ORM annotations, argument-free.

A column whose ``field_name`` matches a registered annotation gets it applied,
and then behaves like any other column — it sorts and filters **in the
database**, which a ``@property`` cannot, being invisible to the ORM.

Everything Django can express is available: ``Subquery`` for a latest value,
``Exists`` for a flag, ``Case``/``When`` for buckets, ``Window`` for a ranking.
The boundary is where the expression is *authored*, not which expressions exist.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from django.db.models import QuerySet


@dataclass(frozen=True)
class Annotation:
    """A registered computed column."""

    name: str
    #: Takes nothing and returns an ORM expression.
    expression: Callable[[], Any]
    #: Declared at registration, because a sorter and a filter widget are
    #: chosen from it before any row exists.
    output_field: Any = None


class AnnotationError(Exception):
    """An annotation was registered twice, named unusably, or asked for by a
    name nothing registered."""


_registry: dict[str, Annotation] = {}


def register_annotation(name: str, *, output_field=None):
    """Register a computed column, as a decorator.

        @register_annotation("order_total", output_field=DecimalField())
        def order_total():
            return F("quantity") * F("unit_price")

    **Argument-free by design.** An argument from configuration would be a path
    from stored data into an ORM call, and therefore a validation surface. The
    developer writes the relation, knows the model, and owns the consequence.

    Raises:
        AnnotationError: the name is taken, or is not lowercase
            ``[a-z][a-z0-9_]*``.
    """
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise AnnotationError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in _registry:
        raise AnnotationError(f"{name!r} is already registered")

    def _register(fn: Callable[[], Any]) -> Callable[[], Any]:
        _registry[name] = Annotation(name=name, expression=fn, output_field=output_field)
        return fn

    return _register


def registered() -> dict[str, Annotation]:
    """Every registered computed column, by name."""
    return dict(_registry)


def is_annotation(name: str) -> bool:
    """Whether this column name is a registered computed column."""
    return name in _registry


def get_annotation(name: str) -> Annotation:
    """The annotation registered under ``name``.

    Raises:
        AnnotationError: nothing is registered under it. A typo fails here
            rather than on every render of the page that names it.
    """
    try:
        return _registry[name]
    except KeyError:
        known = ", ".join(sorted(_registry)) or "none"
        raise AnnotationError(f"no annotation named {name!r} (registered: {known})") from None


def apply(queryset: QuerySet, columns: Iterable[str]) -> QuerySet:
    """Annotate ``queryset`` with whichever columns are registered.

    Columns that are ordinary model fields pass through untouched.
    """
    wanted = {c: _registry[c] for c in columns if c in _registry}
    if not wanted:
        return queryset
    return queryset.annotate(**{name: a.expression() for name, a in wanted.items()})

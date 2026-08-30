"""Per-field widget overrides.

A schema field whose annotation carries no shape — ``list[dict[str, Any]]`` and
its kind — cannot be rendered from the annotation alone. Its owner registers a
template for that one field.
"""
from __future__ import annotations

from pydantic import BaseModel

_registry: dict[tuple[type[BaseModel], str], str] = {}


class OverrideError(Exception):
    """The field does not exist on the schema, or already has an override."""


def register_widget(schema: type[BaseModel], field: str, template: str) -> None:
    """Register ``template`` as the editor for one field of one schema.

    Keyed by the schema class, not its name: a renamed class would otherwise
    orphan its overrides silently, and only the class can say whether the field
    exists.

    Raises:
        OverrideError: ``field`` is not on ``schema``, or already has an
            override.
    """
    if field not in schema.model_fields:
        known = ", ".join(schema.model_fields) or "none"
        raise OverrideError(
            f"{schema.__name__} has no field {field!r} (has: {known})"
        )
    key = (schema, field)
    if key in _registry:
        raise OverrideError(
            f"{schema.__name__}.{field} already has {_registry[key]!r}"
        )
    _registry[key] = template


def overrides_for(schema: type[BaseModel]) -> dict[str, str]:
    """Field name to template, for every override registered on this schema."""
    return {field: tpl for (cls, field), tpl in _registry.items() if cls is schema}

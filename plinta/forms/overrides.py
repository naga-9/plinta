"""Per-field widget overrides.

A schema field whose annotation carries no shape — ``list[dict[str, Any]]`` and
its kind — cannot be rendered from the annotation alone. Its owner registers a
template for that one field.
"""
from __future__ import annotations

_registry: dict[tuple[str, str], str] = {}


class OverrideError(Exception):
    """A field already has a registered override."""


def register_widget(schema_name: str, field: str, template: str) -> None:
    """Register ``template`` as the editor for one field of one schema.

    Raises:
        OverrideError: that field already has one.
    """
    key = (schema_name, field)
    if key in _registry:
        raise OverrideError(f"{schema_name}.{field} already has {_registry[key]!r}")
    _registry[key] = template


def overrides_for(schema_name: str) -> dict[str, str]:
    """Field name to template, for every override registered on this schema."""
    return {field: tpl for (name, field), tpl in _registry.items() if name == schema_name}

"""Derive form fields from a pydantic schema.

Whether a field *may* be edited is decided a layer up and passed in; nothing
here knows what a user is.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel


@dataclass(frozen=True)
class FormField:
    """One row of a derived form."""

    name: str
    widget: str
    annotation: Any
    required: bool
    default: Any
    title: str | None
    description: str | None
    editable: bool = True
    override_template: str | None = None


def unwrap_optional(annotation: Any) -> Any:
    """``Optional[X]`` and ``X | None`` become ``X``; anything else is returned as is."""
    if get_origin(annotation) is Union:
        not_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(not_none) == 1:
            return not_none[0]
    return annotation


def widget_for(annotation: Any) -> str:
    """Pick a widget from a type annotation.

    A container or nested model gets ``json``, because the annotation carries no
    shape a form can render. Those are the fields a component overrides.
    """
    inner = unwrap_optional(annotation)
    if inner is bool:
        return "bool"
    if inner in (int, float):
        return "number"
    if inner is str:
        return "text"
    origin = get_origin(inner)
    if origin in (list, tuple, set, dict, frozenset):
        return "json"
    if isinstance(inner, type) and issubclass(inner, BaseModel):
        return "json"
    return "text"


def fields_for(
    schema: type[BaseModel],
    *,
    editable: set[str] | None = None,
    overrides: dict[str, str] | None = None,
) -> list[FormField]:
    """Describe every field of ``schema``, in declaration order.

    Args:
        schema: the pydantic model to derive from.
        editable: field names the caller permits editing; None means all.
        overrides: field name to template path, replacing the derived widget.
    """
    overrides = overrides or {}
    out: list[FormField] = []
    for name, info in schema.model_fields.items():
        out.append(
            FormField(
                name=name,
                widget=widget_for(info.annotation),
                annotation=info.annotation,
                required=info.is_required(),
                default=None if info.is_required() else info.get_default(call_default_factory=True),
                title=info.title,
                description=info.description,
                editable=editable is None or name in editable,
                override_template=overrides.get(name),
            )
        )
    return out

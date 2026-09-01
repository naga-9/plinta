"""Derive form fields from a pydantic schema.

Whether a field *may* be edited is decided a layer up and passed in; nothing
here knows what a user is.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field as dataclass_field
from typing import Any, Literal, Union, get_args, get_origin

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
    #: The values a closed field may take, for a `choice` widget. Empty for
    #: everything else.
    choices: tuple = dataclass_field(default_factory=tuple)


def unwrap_optional(annotation: Any) -> Any:
    """``Optional[X]`` and ``X | None`` become ``X``; anything else is returned as is."""
    if get_origin(annotation) is Union:
        not_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(not_none) == 1:
            return not_none[0]
    return annotation


def choices_for(annotation: Any) -> tuple:
    """The values a closed annotation admits, or empty.

    `Literal["line", "bar"]` and a `str` enum are both a fixed set somebody
    wrote down. Rendered as a text box — which is what an unrecognised
    annotation gets — the form offers every string and validation refuses all
    but three, so the writer discovers the answer by being wrong.
    """
    inner = unwrap_optional(annotation)
    if get_origin(inner) is Literal:
        return get_args(inner)
    if isinstance(inner, type) and issubclass(inner, enum.Enum):
        return tuple(member.value for member in inner)
    return ()


def widget_for(annotation: Any) -> str:
    """Pick a widget from a type annotation.

    A container or nested model gets ``json``, because the annotation carries no
    shape a form can render. Those are the fields a component overrides.
    """
    inner = unwrap_optional(annotation)
    if choices_for(annotation):
        return "choice"
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
                choices=choices_for(info.annotation),
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

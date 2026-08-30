"""Turn submitted form values back into a schema-validated dict."""
from __future__ import annotations

import json
from typing import Any, get_origin

from pydantic import BaseModel, ValidationError

from plinta.forms.fields import unwrap_optional

#: A cleared form field on a non-optional type: omit it so the schema default
#: applies, rather than sending "" for the schema to reject.
ABSENT = object()


def coerce(raw: Any, annotation: Any) -> Any:
    """Prepare one submitted value for the schema to validate.

    Only the two cases pydantic cannot handle itself. It already turns ``"50"``
    into ``50``, ``"on"`` and ``"true"`` into ``True``, and ``"1.5"`` into
    ``1.5``, so nothing here repeats that — a second coercion would be a second
    contract, differing from the schema's in ways nobody notices.

    A value that cannot be prepared is returned unchanged, so the schema
    reports it as a field error rather than having a default substituted.
    """
    inner = unwrap_optional(annotation)

    # An HTML form sends "" for a field the user cleared.
    if raw is None or raw == "":
        if inner is not annotation:
            return None        # optional: cleared means null
        if inner is str:
            return ""          # empty is a legitimate string
        return ABSENT          # no empty int or bool exists; take the default

    # A container arrives as a JSON string, which pydantic will not parse.
    origin = get_origin(inner)
    is_model = isinstance(inner, type) and issubclass(inner, BaseModel)
    if isinstance(raw, str) and (origin in (list, tuple, set, dict, frozenset) or is_model):
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw
    return raw


def parse(schema: type[BaseModel], data, *, editable: set[str] | None = None):
    """Validate a submitted form against ``schema``.

    Returns ``(config, errors)`` with exactly one of them set. ``config`` is a
    plain dict ready to store; ``errors`` is ``{field: [messages]}``, keyed
    ``_general`` for anything not tied to a field.

    Fields absent from ``data`` are omitted, so the schema's own defaults
    apply. Fields not in ``editable`` are ignored even if submitted.
    """
    values: dict[str, Any] = {}
    for name, info in schema.model_fields.items():
        if editable is not None and name not in editable:
            continue
        if name not in data:
            continue
        value = coerce(data.get(name), info.annotation)
        if value is not ABSENT:
            values[name] = value

    try:
        return schema.model_validate(values).model_dump(), None
    except ValidationError as exc:
        errors: dict[str, list[str]] = {}
        for err in exc.errors():
            key = str(err["loc"][0]) if err["loc"] else "_general"
            errors.setdefault(key, []).append(err["msg"])
        return None, errors

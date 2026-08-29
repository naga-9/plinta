"""Coerce a submitted form back into a schema-validated dict."""
from __future__ import annotations

import json
from typing import Any, get_origin

from pydantic import BaseModel, ValidationError

from plinta.forms.fields import unwrap_optional


def coerce(raw: Any, annotation: Any) -> Any:
    """Coerce one raw POST value to the type its field expects.

    A value that cannot be coerced is returned unchanged so the schema reports
    it as a field error, rather than being silently replaced.
    """
    inner = unwrap_optional(annotation)
    optional = inner is not annotation

    if raw is None or raw == "":
        if optional:
            return None
        return "" if inner is str else None

    if inner is bool:
        return raw in (True, "true", "True", "on", "1", 1)
    if inner is int:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return raw
    if inner is float:
        try:
            return float(raw)
        except (TypeError, ValueError):
            return raw

    origin = get_origin(inner)
    is_model = isinstance(inner, type) and issubclass(inner, BaseModel)
    if origin in (list, tuple, set, dict, frozenset) or is_model:
        if not isinstance(raw, str):
            return raw
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw
    return raw


def parse(schema: type[BaseModel], post, *, editable: set[str] | None = None):
    """Validate a submitted form against ``schema``.

    Returns ``(config, errors)`` with exactly one of them set. ``config`` is a
    plain dict ready to store; ``errors`` is ``{field: [messages]}``, keyed
    ``_general`` for anything not tied to a field.

    Fields absent from ``post`` are omitted, so the schema's own defaults
    apply. Fields not in ``editable`` are ignored even if submitted.
    """
    values: dict[str, Any] = {}
    for name, info in schema.model_fields.items():
        if editable is not None and name not in editable:
            continue
        if name not in post:
            continue
        values[name] = coerce(post.get(name), info.annotation)

    try:
        return schema.model_validate(values).model_dump(), None
    except ValidationError as exc:
        errors: dict[str, list[str]] = {}
        for err in exc.errors():
            key = str(err["loc"][0]) if err["loc"] else "_general"
            errors.setdefault(key, []).append(err["msg"])
        return None, errors

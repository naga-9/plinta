"""The API envelope: one response shape for every endpoint.

    {"success": true}
    {"success": true,  "data": {...}}
    {"success": false, "errors": {field: [msg, ...]}}

A client reads ``success`` first. Unfielded messages are keyed ``_general``.
"""
from django.http import JsonResponse
from pydantic import BaseModel, ConfigDict, ValidationError


class EnvelopeOK(BaseModel):
    """Success envelope, for the OpenAPI schema."""

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    data: dict | None = None


class EnvelopeError(BaseModel):
    """Failure envelope, for the OpenAPI schema."""

    model_config = ConfigDict(extra="forbid")

    success: bool = False
    errors: dict[str, list[str]] | str


def json_response(*, data=None, errors=None, status=None) -> JsonResponse:
    """Build an envelope response.

    Args:
        data: success payload; omitted when None.
        errors: ``{field: [messages]}`` or a string, which is keyed
            ``_general``. Any value flips ``success`` to False.
        status: defaults to 200, or 400 when errors are present.
    """
    success = errors is None
    payload: dict = {"success": success}
    if data is not None:
        payload["data"] = data
    if errors is not None:
        payload["errors"] = {"_general": [errors]} if isinstance(errors, str) else errors
    return JsonResponse(payload, status=status or (200 if success else 400))


def parse_request(request, schema):
    """Validate a JSON request body against a pydantic schema.

    Returns ``(payload, error_response)`` with exactly one of them set::

        payload, err = parse_request(request, MySchema)
        if err:
            return err
    """
    try:
        return schema.model_validate_json(request.body or b"{}"), None
    except ValidationError as exc:
        errors: dict[str, list[str]] = {}
        for err in exc.errors():
            key = str(err["loc"][0]) if err["loc"] else "_general"
            errors.setdefault(key, []).append(err["msg"])
        return None, json_response(errors=errors, status=400)
    except ValueError as exc:
        return None, json_response(errors=f"Invalid JSON: {exc}", status=400)

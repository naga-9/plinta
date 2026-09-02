"""Seven handlers, for every DataSource there will ever be.

Not seven per model: a `DataSourceField` already records the path, label, type
and filterability, which is a serializer definition. Registering a DataSource
publishes it and there is no further step — and no second description of the
same model to drift from the first (§15.1).

**Permissions are the only gate.** There is no field-level API flag, because
`view_{model}` and `view_{model}_{field}` answer both questions already and a
second mechanism answering the same question is one that drifts. Every entry
point filters, not just the row fetch — which is what makes the absence of a
flag safe:

    /data/               the model permission; an unprivileged caller gets an
                         empty list and learns no model or field names
    /data/{ds}/schema/   get_available_fields
    /data/{ds}/          get_queryset

Discovery must not reveal what access denies, for the same reason the menu is
filtered.

**Writes go through the block write pipeline**, so an API edit is authorised,
validated, audited and notified exactly like a UI edit, with no code here to
keep in step.
"""
from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.http import Http404
from ninja import Body, Router, Status

from plinta.blocks.write import WriteDenied
from plinta.datasources.kinds import kind_of
from plinta.datasources.models import DataSource
from plinta.renderers.values import raw

router = Router(tags=["data"])

#: What performed the write, carried on both events so a trail can tell an
#: API edit from a screen edit.
SOURCE = "api"


def _datasource(name: str) -> DataSource:
    """The published DataSource called ``name``.

    Unpublished is a **404**, not a 403: `show_in_api` is curation rather than
    access control (§6.1a), so a caller has no business learning that a
    DataSource exists but was not chosen for them.
    """
    source = DataSource.objects.filter(
        name=name, is_active=True, show_in_api=True
    ).first()
    if source is None:
        raise Http404("no such data source")
    return source


def _row(source: DataSource, pk, user):
    from plinta.datasources.services import get_queryset

    # Through `get_queryset`, so a row this caller may not see is missing
    # rather than forbidden — the pk is a number somebody can guess, and a
    # 403 would confirm the guess.
    row = get_queryset(source, user).filter(pk=pk).first()
    if row is None:
        raise Http404("no such record")
    return row


def _serialise(row, fields, model) -> dict[str, Any]:
    """One row as the fields hold it, never as a person reads it.

    `raw`, not `cell`: a machine wants `8.75` and an ISO date, not `£8.75` and
    `3 March`. The formatted half belongs to the screen.
    """
    body = {"id": row.pk}
    for field in fields:
        kind = kind_of(model, field.field_name, getattr(field, "sorter", "") or "string")
        body[field.field_name] = raw(row, field.field_name, kind)
    return body


@router.get("/data/", url_name="datasources")
def datasources(request):
    """The DataSources this caller may read.

    Filtered by the model permission, so an unprivileged caller gets an empty
    list and learns no model or field names from it.
    """
    from plinta.permissions import can

    out = []
    for source in DataSource.objects.filter(is_active=True, show_in_api=True):
        model = source.model
        # A model class, not a row: `can` reads that as "may they at all?",
        # which is tier one alone and exactly what a listing should ask.
        if model is None or not can(request.user, "view", model):
            continue
        out.append({
            "name": source.name,
            "label": source.label,
            "description": source.description,
        })
    return out


@router.get("/data/{ds}/schema/", url_name="schema")
def schema(request, ds: str):
    """The fields of ``ds`` this caller may see, and how each behaves."""
    from plinta.datasources.services import get_available_fields, writable_fields

    source = _datasource(ds)
    model = source.model
    writable = writable_fields(source, request.user)
    return {
        "name": source.name,
        "label": source.label,
        "fields": [
            {
                "name": field.field_name,
                "label": field.label,
                "type": kind_of(
                    model, field.field_name, getattr(field, "sorter", "") or "string"
                ),
                "filterable": field.filterable,
                "writable": field.field_name in writable,
            }
            for field in get_available_fields(source, request.user)
        ],
    }


@router.get("/data/{ds}/", url_name="list")
def list_rows(request, ds: str):
    """The rows of ``ds`` this caller may see, filtered, ordered and paged."""
    from plinta.contrib.api import query
    from plinta.datasources.services import get_available_fields, get_queryset

    source = _datasource(ds)
    model = source.model
    fields = get_available_fields(source, request.user)
    params = request.GET

    rows = get_queryset(source, request.user)
    rows = query.searched(rows, params.get("search", ""), source, request.user)
    rows = query.filtered(rows, params.dict(), fields, model)
    rows = query.ordered(rows, params.get("order", ""), fields)

    page, meta = query.page_of(
        rows, _int(params.get("page"), 1), _int(params.get("size"), 0)
    )
    return {
        "results": [_serialise(row, fields, model) for row in page],
        **meta,
    }


@router.get("/data/{ds}/{pk}/", url_name="detail")
def read_row(request, ds: str, pk: str):
    from plinta.datasources.services import get_available_fields

    source = _datasource(ds)
    return _serialise(
        _row(source, pk, request.user),
        get_available_fields(source, request.user),
        source.model,
    )


#: `Body(...)` and not a bare `dict`: ninja reads an un-annotated dict as a
#: *query* parameter, so the payload never arrives and every write answers 422
#: saying the body is missing. A `Schema` is not an option — the fields differ
#: per DataSource, which is the whole point of generating this.
PAYLOAD = Body(..., description="The fields being written, by column name.")


@router.post("/data/{ds}/", url_name="create", response={201: dict})
def create_row(request, ds: str, body: dict = PAYLOAD):
    source = _datasource(ds)
    instance = source.model()
    return Status(201, _write(request, source, instance, body))


@router.patch("/data/{ds}/{pk}/", url_name="update")
def update_row(request, ds: str, pk: str, body: dict = PAYLOAD):
    source = _datasource(ds)
    return _write(request, source, _row(source, pk, request.user), body)


@router.delete("/data/{ds}/{pk}/", url_name="delete", response={204: None})
def delete_row(request, ds: str, pk: str):
    from plinta.blocks.write import delete

    source = _datasource(ds)
    delete(_row(source, pk, request.user), request.user, source=SOURCE)
    return Status(204, None)


def _write(request, source: DataSource, instance, body: dict):
    """Apply ``body`` through the write pipeline and answer with the row.

    Fields the caller may not write are **dropped rather than refused**, the
    same as the UI: a payload naming one is answered with the write it was
    allowed to make, and the response says what the row now holds.
    """
    from plinta.blocks.submit import coerced
    from plinta.blocks.write import write
    from plinta.datasources.services import get_available_fields, writable_fields

    writable = writable_fields(source, request.user)
    asked = {name: value for name, value in (body or {}).items() if name in writable}
    saved, _ = write(instance, coerced(source, asked, request.user), request.user,
                     source=SOURCE)
    return _serialise(saved, get_available_fields(source, request.user), source.model)


def _int(value, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback



def register_errors(api) -> None:
    """Map plinta's refusals onto ninja's own status codes.

    Registered on the `NinjaAPI` rather than per handler, so a new endpoint
    cannot forget one. `WriteDenied` is 403 and not 401: the caller is known,
    and it is what they asked for that is refused.
    """
    from ninja.errors import HttpError

    @api.exception_handler(WriteDenied)
    def _denied(request, exc):
        return api.create_response(request, {"detail": str(exc)}, status=403)

    @api.exception_handler(ValidationError)
    def _invalid(request, exc):
        # Ninja's own shape for a rejected body, so one 422 contract covers
        # both its validation and the model's (§15.2).
        detail = [
            {"loc": ["body", field], "msg": message}
            for field, messages in getattr(exc, "message_dict", {}).items()
            for message in messages
        ]
        return api.create_response(
            request, {"detail": detail or [{"loc": ["body"], "msg": str(exc)}]},
            status=422,
        )

    @api.exception_handler(Http404)
    def _missing(request, exc):
        return api.create_response(request, {"detail": str(exc)}, status=404)

    @api.exception_handler(HttpError)
    def _http(request, exc):
        return api.create_response(
            request, {"detail": str(exc)}, status=exc.status_code
        )

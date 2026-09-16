"""One card's conversation with the server: its rows, its writes, its form,
its saved views.

Everything here is **placement-scoped**: the placement is what knows the
view, the context filter and the tab, so the server reads them from the row
rather than trusting them from the query string, and a write cannot reach a
card a read could not.
"""
from __future__ import annotations

import json
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from plinta.pages.models import PageBlock
from plinta.pages.rendering import default_filters, filter_q, resolve_filters
from plinta.shell.views.page import closes_a_layer, submitted_filters, visible_page
from plinta.shell.views.returning import back_to

#: How a browser posts a form. Both reach `request.POST`.
FORM_TYPES = ("application/x-www-form-urlencoded", "multipart/form-data")


def placement_of(request: HttpRequest, pk: int, placement: int):
    """The page, the placement and the component behind one card.

    Shared by both halves of a card's conversation with the server, so a
    write cannot reach a placement a read could not.
    """
    from plinta.components.registry import find

    page = visible_page(request, pk)
    try:
        slot = page.placements.select_related("block", "block__data_source").get(
            pk=placement, is_visible=True
        )
    except PageBlock.DoesNotExist as exc:
        raise Http404("no such block on this page") from exc

    component = find(slot.block.component_type)
    if component is None or slot.block.data_source is None:
        raise Http404("that block has nothing to fetch")
    return page, slot, component


@login_required
def block_data(request: HttpRequest, pk: int, placement: int) -> JsonResponse:
    """The rows one card asks for, as JSON.

    **Placement-scoped, not block-scoped.** The placement is what knows the
    view, the context filter and the tab, so the server reads them from the
    row rather than trusting them from the query string — a detail page's
    context filter travelling as a parameter would be a client that can
    rescope its own card. v1's endpoint was block-scoped and had to re-apply
    `base_filter` at the end for exactly that reason.

    Gated by the **page's** permission, the same `visible_page` a render uses,
    so reachability over the wire and on the screen cannot drift apart.
    """
    from plinta.blocks.feed import feed, requested
    from plinta.blocks.rendering import chosen_view, effective_config, views_for
    from plinta.blocks.narrowing import narrowing_for

    page, slot, component = placement_of(request, pk, placement)
    asked = requested(request.GET)
    views = views_for([slot.block], request.user).get(slot.block_id, [])
    view = chosen_view(views, request.user, asked["view"], slot.default_view_id)

    config = component.config_schema(
        **effective_config(slot.block, request.user, view)
    )
    values = submitted_filters(request, page) or default_filters(page, request.user)
    narrowing = filter_q(page, values, request.user) & Q(
        **resolve_filters(slot.context_filter, request.user, None)
    )

    return JsonResponse(
        feed(
            component,
            config,
            request.user,
            datasource=slot.block.data_source,
            narrow=narrowing_for(slot.block, request.user, narrowing),
            asked=asked,
        )
    )


@login_required
@require_POST
def block_write(request: HttpRequest, pk: int, placement: int) -> JsonResponse:
    """One write from one card, through the pipeline.

    The mirror of `block_data`, and deliberately the same shape for every
    component that writes: a record and the fields being written is what a
    dragged kanban card, an edited table cell and a submitted form all are
    (§8.11).

    Two content types in, and the answer matches the question. A widget
    sends JSON and gets JSON: the row, or the errors keyed by field. A form
    posts itself and gets the form back, drawn again — saying what was wrong
    beside each field, or that it saved. With `X-Up-Validate` the form is
    only asking, and nothing is saved. One pipeline behind both.

    Narrowed by the **block's** own filters, never by the page's filter bar.
    A base filter is a boundary — a card scoped to one region may not write
    outside it — while the bar is a viewer's passing choice, and a write that
    failed because of what somebody typed into a filter box would be a bug
    nobody could reproduce.
    """
    from plinta.blocks.narrowing import narrowing_for
    from plinta.blocks.submit import check, submit, submitted, submitted_form
    from plinta.blocks.write import WriteDenied

    _, slot, component = placement_of(request, pk, placement)

    as_form = request.content_type in FORM_TYPES
    if request.content_type == "application/json":
        try:
            body = json.loads(request.body or b"{}")
        except ValueError:
            return JsonResponse({"detail": "unreadable body"}, status=400)
        if not isinstance(body, dict):
            return JsonResponse({"detail": "expected an object"}, status=400)
        record, values = submitted(body)
    elif as_form:
        record, values = submitted_form(slot.block.data_source, request.POST)
    else:
        # §15.3: one shape for writes, so there is one thing to protect —
        # JSON as a widget sends it, or that same shape as a browser posts a
        # form.
        return JsonResponse(
            {"detail": "send application/json or a form"}, status=415
        )

    if not component.writes:
        # The component says it cannot, which is not the same as this viewer
        # may not: a chart refuses everyone, permission refuses someone.
        return JsonResponse(
            {"detail": f"{slot.block.component_type} does not write"}, status=405
        )

    context = Q(**resolve_filters(slot.context_filter, request.user, None))
    narrow = narrowing_for(slot.block, request.user, context)
    asking = as_form and bool(request.headers.get("X-Up-Validate"))
    try:
        if asking:
            errors = check(
                slot.block, request.user, datasource=slot.block.data_source,
                record=record, values=values, narrow=narrow,
            )
            written = {"record": record, "row": None, "errors": errors}
        else:
            written = submit(
                slot.block, request.user, datasource=slot.block.data_source,
                record=record, values=values, narrow=narrow,
            )
    except WriteDenied as exc:
        # A refusal and a rejection are different answers: this one will not
        # succeed however the values are changed.
        if as_form:
            return _record_form(
                request, pk, placement, record=record, values=values,
                errors={name: [str(exc)] for name in exc.denied_fields or ["__all__"]},
                status=403,
            )
        return JsonResponse(
            {"detail": str(exc), "fields": exc.denied_fields}, status=403
        )

    status = 200 if written["errors"] is None else 422
    if not as_form:
        return JsonResponse(written, status=status)
    if written["errors"] is not None or asking:
        return _record_form(
            request, pk, placement, record=record, values=values,
            errors=written["errors"] or {}, status=status,
        )
    # Saved. The form is drawn again about the row it now is — a create has
    # become an edit — and says so. Inside a layer, that is also "done": the
    # layer closes, with the record for whoever opened it.
    response = _record_form(request, pk, placement, record=written["record"], saved=True)
    if closes_a_layer(request):
        response["X-Up-Accept-Layer"] = json.dumps({"record": written["record"]})
    return response


@login_required
def block_options(
    request: HttpRequest, pk: int, placement: int, field: str
) -> JsonResponse:
    """What one relation column may be set to, for a picker that searches.

    A short list travels with the columns and never reaches here; this is for
    the ones too long to send, which is the only reason the endpoint exists.

    The same queryset the write resolves against, so the picker cannot offer
    what the save would refuse, nor hide what it would accept.
    """
    from plinta.datasources.services import writable_fields as writable
    from plinta.datasources.choices import choosable, options

    _, slot, component = placement_of(request, pk, placement)
    if not component.writes or field not in writable(slot.block.data_source,
                                                     request.user):
        # Not editable here is not "no options": it is a column nobody should
        # be asking about, and answering would say what the rows are to
        # somebody who may not change them.
        raise Http404("that column is not editable here")

    rows = choosable(slot.block.data_source.model, field, request.user)
    if rows is None:
        raise Http404("that column is not a relation")
    return JsonResponse(
        {"options": options(rows, search=request.GET.get("q", ""))}
    )


@login_required
def block_form(request: HttpRequest, pk: int, placement: int) -> HttpResponse:
    """One record's form, for a card that opens one.

    The **same** form a detail page draws, asked for after the page has
    loaded: a pencil on a row and a button on a card header both come here,
    and so will a kanban card. Which fields it offers is the form's answer,
    not the caller's, so "edit" and "view" are one request (§8.11).

    ``?record=`` names the row. Without one it is a create, which is why the
    two buttons need no separate endpoint between them.

    Its DataSource is the placement's own. A block edits records of its own
    DataSource and never another's (§6.7), so there is nothing here to point
    somewhere else.
    """
    return _record_form(request, pk, placement, record=request.GET.get("record") or None)


def _record_form(
    request: HttpRequest,
    pk: int,
    placement: int,
    *,
    record: Any,
    values: dict | None = None,
    errors: dict | None = None,
    saved: bool = False,
    status: int = 200,
) -> HttpResponse:
    """One record's form, drawn — fresh, or again after a post.

    ``record`` names the row, or nothing for a create. ``values`` and
    ``errors`` are a post's, for drawing the form as it was submitted with
    what was wrong beside each field; ``saved`` says the post landed.
    """
    from plinta.blocks.narrowing import narrowing_for
    from plinta.components.form import FormComponent
    from plinta.components.registry import find as find_component
    from plinta.datasources.services import get_queryset

    _, slot, opener = placement_of(request, pk, placement)
    source = slot.block.data_source

    row = None
    if record is not None:
        # Reached through the rows this viewer may see, narrowed the way the
        # block is — the same gate the write applies, so a form cannot be
        # opened on a row that could not then be saved.
        context = Q(**resolve_filters(slot.context_filter, request.user, None))
        rows = narrowing_for(slot.block, request.user, context)(
            get_queryset(source, request.user, columns=[])
        )
        try:
            row = rows.filter(pk=record).first()
        except (ValueError, TypeError):
            row = None
        if row is None:
            raise Http404("no such record here")

    component = find_component("form_plinta") or FormComponent()
    # The component that opens the form says which layout to draw it with,
    # and nothing else about it: what a form is stays the form's business.
    opened = opener.validate(slot.block.config)
    config = component.config_schema(
        layout=getattr(opened, "form_layout", "") or ""
    )
    form = component.render(
        config,
        request.user,
        datasource=source,
        record=row,
        write_url=f"/pages/{pk}/blocks/{placement}/write/",
        options_url=f"/pages/{pk}/blocks/{placement}/options/",
        values=values,
        errors=errors,
        saved=saved,
    )
    # Wrapped here and not in the form's template: the same template draws
    # a form block on a detail page, and `up-main` there would make the
    # block the page's main element. This response is only ever a layer's,
    # or the swap of a form that posted — which takes the form alone.
    return HttpResponse(f'<div class="pl-dialog" up-main>{form}</div>', status=status)


@login_required
def block_views(request: HttpRequest, pk: int, placement: int) -> HttpResponse:
    """Manage the saved views on one card's block.

    A plain form, posted and redirected rather than fetched: saving a view
    changes what the card shows, and the page redraws for the same reason a
    filter change does (§7.12). The dialog is where it is *drawn*, not how it
    is submitted.

    The fields come from the component's own schema, so this screen has no
    idea what a table is (§12.3).
    """
    from plinta.blocks import saved_views

    page, slot, component = placement_of(request, pk, placement)
    mine = saved_views.visible_views(slot.block, request.user)

    if request.method == "POST":
        return _save_view(request, page, slot, component, mine)

    chosen = next(
        (v for v in mine if str(v.pk) == (request.GET.get("view") or "")), None
    )
    return render(
        request,
        "plinta/blocks/view_editor.html",
        _view_editor(request, slot, component, mine, chosen),
    )


def _view_editor(request, slot, component, mine, view, errors=None) -> dict:
    """What the editor draws, opened on ``view`` — fresh, or again with
    ``errors`` after a post. One place, so the two cannot drift."""
    from plinta.blocks import saved_views
    from plinta.forms.layouts import layout_for
    from plinta.permissions import can

    # Once: it reads the schema and asks which columns this viewer may see.
    settings = saved_views.settings_for(component, slot.block, request.user, view)
    return {
        "views": mine,
        "view": view,
        "settings": settings,
        "settings_by_name": {s["name"]: s for s in settings},
        "layout": layout_for(component.config_schema),
        "may_publish": saved_views.may_publish(request.user),
        "may_default": saved_views.may_default(request.user),
        "may_delete": view is not None and can(request.user, "delete", view),
        "action": request.path,
        # Where the layer was opened over, to go back to (`back_to`).
        "next": request.POST.get("next") or request.GET.get("next") or "",
        "errors": errors or {},
    }


def _save_view(request: HttpRequest, page, slot, component, mine):
    """Create, update or delete one view, then send the viewer back to it."""
    from plinta.blocks import saved_views
    from plinta.blocks.write import WriteDenied
    from plinta.forms.parse import parse
    from plinta.permissions import can

    block = slot.block
    schema = component.config_schema
    asked = request.POST.get("view") or ""
    view = next((v for v in mine if str(v.pk) == asked), None)

    if request.POST.get("action") == "delete":
        if view is None or not can(request.user, "delete", view):
            raise Http404("no such view")
        view.delete()
        return redirect(back_to(request, page.get_absolute_url()))

    # A blank control is absent, which is the whole of "same as the block".
    submitted = saved_views.submitted_settings(schema, request.POST)
    config, errors = parse(schema, submitted)
    if errors:
        return render(
            request,
            "plinta/blocks/view_editor.html",
            _view_editor(request, slot, component, mine, view, errors),
            status=422,
        )

    # `parse` validates and returns the **whole** config, defaults included,
    # which is what a block inspector wants and the opposite of what a delta
    # is. Only what was actually submitted survives.
    overridden = {name: config[name] for name in submitted if name in config}

    try:
        saved = saved_views.save(
            block,
            request.user,
            name=request.POST.get("name") or "Untitled",
            values=overridden,
            pinned=saved_views.pinned_settings(schema),
            view=view,
            public=bool(request.POST.get("public")),
            default=bool(request.POST.get("is_default")),
        )
    except WriteDenied as exc:
        return HttpResponseForbidden(str(exc))

    # Back to where the layer was opened, on what was just saved — and on
    # *this* placement's parameter, so the other card keeps its own view.
    return redirect(
        back_to(request, page.get_absolute_url(), **{f"b{slot.pk}_view": saved.pk})
    )

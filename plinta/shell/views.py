"""The views the shell serves: a page, and nothing else yet.

A page is resolved by **id**; the slug in the URL is decorative and is not
checked, so renaming a page does not break a link someone shared (§9.0).
"""
from __future__ import annotations

import json
from typing import Any

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import redirect, render

from django.db.models import Q

from plinta.pages.models import Page, PageBlock, PageType
from plinta.pages.rendering import (
    controls_of,
    default_filters,
    drawn_controls,
    filter_q,
    remember_filters,
    render_page,
    resolve_filters,
    saved_filter_sets,
)
from plinta.permissions import can

#: Query parameters the filter bar uses for itself.
RESERVED = {"tab", "page", "sort", "reset", "view", "filterset"}


def submitted_filters(
    request: HttpRequest, page: Page, source: Any = None
) -> dict[str, Any] | None:
    """The filter values submitted, or None if none were.

    ``source`` is the query string by default and the POST body when the
    editor is saving a set — the same controls either way, so the same
    parsing reads them and there is one place that knows how a range or a
    multi-select spells itself.

    Only fields the page declares are read. A query string naming anything
    else is ignored, because the bar is what the page exposes and a URL is
    not (§9.4).

    A control whose widget takes several values is read with `getlist`; every
    other with `get`. An empty selection reaches here as an empty list, which
    `filter_q` drops — so clearing a multi-select clears the filter
    rather than reapplying the default.
    """
    from plinta.pages.widgets import find

    sent_in = request.GET if source is None else source
    declared = {control.field_name: control for control in controls_of(page)}
    sent: dict[str, Any] = {}
    for name in sent_in:
        if name in RESERVED or name not in declared:
            continue
        widget = find(declared[name].widget)
        if widget is not None and widget.bounds:
            continue  # read below, from its two keys rather than from this one
        if widget is not None and widget.multiple:
            # `GET[name]` keeps only the last of a repeated key, so a
            # multi-valued control would silently filter on whichever option
            # happened to be last in the form.
            sent[name] = [v for v in sent_in.getlist(name) if v != ""]
        else:
            sent[name] = sent_in[name]

        # A control offering a choice of operator submits it as its own key,
        # `<field>__op`. The **path** is never assembled from input: only
        # which operator, and only from what this control offers.
        control = declared[name]
        if control.allowed_lookups:
            asked = sent_in.get(f"{name}__op", "")
            sent[name] = {
                "op": asked if asked in control.allowed_lookups else control.lookup,
                "value": sent[name],
            }

    # A range submits `<field>__from` and `<field>__to`: one control, two
    # keys, so it cannot be read by looking for its own field name.
    for name, control in declared.items():
        widget = find(control.widget)
        if widget is None or not widget.bounds:
            continue
        bounds = {
            edge: sent_in.get(f"{name}__{edge}", "").strip()
            for edge in ("from", "to")
        }
        if any(bounds.values()):
            sent[name] = {k: v for k, v in bounds.items() if v}
        elif f"{name}__from" in sent_in or f"{name}__to" in sent_in:
            # Present and empty is a cleared range, not an absent one — the
            # same reason a multi-select ships a hidden companion.
            sent[name] = {}
    return sent or None


def bound_record(page: Page, request: HttpRequest, record_pk=None):
    """The row a detail page is about, or None.

    Taken from the URL when the path carries one, otherwise from the query
    parameter the page names in `context_param` — a detail page reached from
    somewhere else often arrives as `?id=7`.

    Raises:
        Http404: the page names no model, the row does not exist, or the
            viewer may not see it. A 404 rather than a 403 throughout: saying
            a record exists but is not yours is itself a disclosure.
    """
    if record_pk is None and page.context_param:
        record_pk = request.GET.get(page.context_param)
    if record_pk in (None, ""):
        return None

    source = page.primary_data_source
    if source is None or source.model is None:
        raise Http404("this page names no model to show")

    row = source.model._default_manager.filter(pk=record_pk).first()
    if row is None or not can(request.user, "view", row):
        raise Http404("no such record")
    return row


def chosen_set(page: Page, request: HttpRequest, sets: list):
    """The saved filter set the viewer picked, or None.

    Matched against what they may see rather than fetched by id, so a set
    somebody else owns is simply not found — the id is guessable, and a
    refusal would confirm it exists.
    """
    asked = request.GET.get("filterset")
    if not asked:
        return None
    return next((s for s in sets if str(s.pk) == asked), None)


def visible_page(request: HttpRequest, pk: int) -> Page:
    """The page, or a 404.

    A page the viewer may not see is a 404 rather than a 403: telling someone
    a page exists but is not theirs is itself a disclosure.
    """
    try:
        page = Page.objects.select_related("primary_data_source").get(pk=pk)
    except Page.DoesNotExist as exc:
        raise Http404("no such page") from exc
    if not page.is_active or not can(request.user, "view", page):
        raise Http404("no such page")
    return page


@login_required
def filter_options(request: HttpRequest, pk: int) -> JsonResponse:
    """The options every control should offer, given what is chosen now.

    So the cascade can happen while somebody is choosing rather than only
    after they apply: pick a title, see which shops sold it, then pick one.
    Applying first to find out what to apply is the wrong order.

    Private UI transport (§15.4) — a plain view, not part of the public API,
    and free to change with the interface it serves. It computes nothing of
    its own: `drawn_controls` is what the page render already calls, so the
    scoping and the cascade cannot drift from what a reload would show.
    """
    page = visible_page(request, pk)
    values = submitted_filters(request, page) or {}
    return JsonResponse(
        {
            drawn.control.field_name: drawn.options
            for drawn in drawn_controls(page, values, request.user)
            if drawn.options
        }
    )


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

    Narrowed by the **block's** own filters, never by the page's filter bar.
    A base filter is a boundary — a card scoped to one region may not write
    outside it — while the bar is a viewer's passing choice, and a write that
    failed because of what somebody typed into a filter box would be a bug
    nobody could reproduce.
    """
    from plinta.blocks.narrowing import narrowing_for
    from plinta.blocks.submit import submit, submitted
    from plinta.blocks.write import WriteDenied

    if request.content_type != "application/json":
        # §15.3: one content type for writes, so there is one thing to parse
        # and one thing to protect.
        return JsonResponse(
            {"detail": "send application/json"}, status=415
        )
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"detail": "unreadable body"}, status=400)
    if not isinstance(body, dict):
        return JsonResponse({"detail": "expected an object"}, status=400)

    _, slot, component = placement_of(request, pk, placement)
    if not component.writes:
        # The component says it cannot, which is not the same as this viewer
        # may not: a chart refuses everyone, permission refuses someone.
        return JsonResponse(
            {"detail": f"{slot.block.component_type} does not write"}, status=405
        )

    record, values = submitted(body)
    context = Q(**resolve_filters(slot.context_filter, request.user, None))
    try:
        written = submit(
            slot.block,
            request.user,
            datasource=slot.block.data_source,
            record=record,
            values=values,
            narrow=narrowing_for(slot.block, request.user, context),
        )
    except WriteDenied as exc:
        # A refusal and a rejection are different answers: this one will not
        # succeed however the values are changed.
        return JsonResponse(
            {"detail": str(exc), "fields": exc.denied_fields}, status=403
        )
    return JsonResponse(written, status=200 if written["errors"] is None else 422)


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
    from plinta.blocks.narrowing import narrowing_for
    from plinta.components.form import FormComponent
    from plinta.components.registry import find as find_component
    from plinta.datasources.services import get_queryset

    _, slot, opener = placement_of(request, pk, placement)
    source = slot.block.data_source

    record = None
    asked = request.GET.get("record") or ""
    if asked:
        # Reached through the rows this viewer may see, narrowed the way the
        # block is — the same gate the write applies, so a form cannot be
        # opened on a row that could not then be saved.
        context = Q(**resolve_filters(slot.context_filter, request.user, None))
        rows = narrowing_for(slot.block, request.user, context)(
            get_queryset(source, request.user, columns=[])
        )
        try:
            record = rows.filter(pk=asked).first()
        except (ValueError, TypeError):
            record = None
        if record is None:
            raise Http404("no such record here")

    component = find_component("form_plinta") or FormComponent()
    # The component that opens the form says which layout to draw it with,
    # and nothing else about it: what a form is stays the form's business.
    opened = opener.validate(slot.block.config)
    config = component.config_schema(
        layout=getattr(opened, "form_layout", "") or ""
    )
    return HttpResponse(
        component.render(
            config,
            request.user,
            datasource=source,
            record=record,
            write_url=f"/pages/{pk}/blocks/{placement}/write/",
            options_url=f"/pages/{pk}/blocks/{placement}/options/",
        )
    )


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
    from plinta.forms.layouts import layout_for
    from plinta.permissions import can

    page, slot, component = placement_of(request, pk, placement)
    block = slot.block
    mine = saved_views.visible_views(block, request.user)
    chosen = next(
        (v for v in mine if str(v.pk) == (request.GET.get("view") or "")), None
    )

    if request.method == "POST":
        return _save_view(request, page, slot, component, mine)

    # Once: it reads the schema and asks which columns this viewer may see.
    settings = saved_views.settings_for(component, block, request.user, chosen)
    return render(
        request,
        "plinta/blocks/view_editor.html",
        {
            "cls": _classes(),
            "views": mine,
            "view": chosen,
            "settings": settings,
            "settings_by_name": {s["name"]: s for s in settings},
            "layout": layout_for(component.config_schema),
            "may_publish": saved_views.may_publish(request.user),
            "may_default": saved_views.may_default(request.user),
            "may_delete": chosen is not None and can(request.user, "delete", chosen),
            "action": f"/pages/{pk}/blocks/{placement}/views/",
            "errors": {},
        },
    )


def _classes() -> dict:
    from plinta.utils.styles import classes

    return classes()


def _save_view(request: HttpRequest, page, slot, component, mine):
    """Create, update or delete one view, then send the viewer back to it."""
    from plinta.blocks import saved_views
    from plinta.blocks.write import WriteDenied
    from plinta.forms.layouts import layout_for
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
        return redirect(page.get_absolute_url())

    # A blank control is absent, which is the whole of "same as the block".
    submitted = saved_views.submitted_settings(schema, request.POST)
    config, errors = parse(schema, submitted)
    if errors:
        settings = saved_views.settings_for(component, block, request.user, view)
        return render(
            request,
            "plinta/blocks/view_editor.html",
            {
                "cls": _classes(),
                "views": mine,
                "view": view,
                "settings": settings,
                "settings_by_name": {s["name"]: s for s in settings},
                "layout": layout_for(component.config_schema),
                "may_publish": saved_views.may_publish(request.user),
                "may_default": saved_views.may_default(request.user),
                "may_delete": view is not None and can(request.user, "delete", view),
                "action": request.path,
                "errors": errors,
            },
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

    # Back to the page, opened on what was just saved — and on *this*
    # placement's parameter, so the other card keeps its own view.
    return redirect(
        f"{page.get_absolute_url()}?b{slot.pk}_view={saved.pk}"
    )


@login_required
def page_filters(request: HttpRequest, pk: int) -> HttpResponse:
    """Manage the saved filter sets on one page.

    Page-scoped, not placement-scoped: a filter set belongs to the bar, and
    the bar belongs to the page. Otherwise the same shape as the view editor —
    a plain form in the dialog, posted and redirected, because saving one
    changes what the page shows.

    Opened with the current query string, so "save these filters" means the
    ones on screen rather than an empty form to fill in again.
    """
    from plinta.pages import filter_sets
    from plinta.permissions import can

    page = visible_page(request, pk)
    mine = filter_sets.visible_sets(page, request.user)
    chosen = next(
        (s for s in mine if str(s.pk) == (request.GET.get("set") or "")), None
    )

    if request.method == "POST":
        return _save_filter_set(request, page, mine)

    # What the bar is showing: the set being edited, else whatever the URL
    # carries, else where the page starts.
    values = (
        dict(chosen.values)
        if chosen
        else (submitted_filters(request, page) or default_filters(page, request.user))
    )
    return render(
        request,
        "plinta/pages/filter_set_editor.html",
        {
            "cls": _classes(),
            "page": page,
            "sets": mine,
            "set": chosen,
            "filter_controls": drawn_controls(page, values, request.user),
            "may_publish": filter_sets.may_publish(request.user),
            "may_default": filter_sets.may_default(request.user),
            "may_delete": chosen is not None and can(request.user, "delete", chosen),
            "action": f"/pages/{pk}/filters/",
            "errors": {},
        },
    )


def _save_filter_set(request: HttpRequest, page, mine):
    """Create, update or delete one set, then send the viewer back to it."""
    from django.core.exceptions import ValidationError

    from plinta.blocks.write import WriteDenied
    from plinta.pages import filter_sets
    from plinta.permissions import can

    asked = request.POST.get("set") or ""
    existing = next((s for s in mine if str(s.pk) == asked), None)

    if request.POST.get("action") == "delete":
        if existing is None or not can(request.user, "delete", existing):
            raise Http404("no such filter set")
        existing.delete()
        return redirect(page.get_absolute_url())

    try:
        saved = filter_sets.save(
            page,
            request.user,
            name=request.POST.get("name") or "Untitled",
            values=submitted_filters(request, page, request.POST) or {},
            filter_set=existing,
            public=bool(request.POST.get("public")),
            default=bool(request.POST.get("is_default")),
        )
    except WriteDenied as exc:
        return HttpResponseForbidden(str(exc))
    except ValidationError as exc:
        return render(
            request,
            "plinta/pages/filter_set_editor.html",
            {
                "cls": _classes(),
                "page": page,
                "sets": mine,
                "set": existing,
                "filter_controls": drawn_controls(
                    page,
                    submitted_filters(request, page, request.POST) or {},
                    request.user,
                ),
                "may_publish": filter_sets.may_publish(request.user),
                "may_default": filter_sets.may_default(request.user),
                "may_delete": existing is not None
                and can(request.user, "delete", existing),
                "action": request.path,
                "errors": exc.message_dict,
            },
            status=422,
        )

    return redirect(f"{page.get_absolute_url()}?filterset={saved.pk}")


def page_view(
    request: HttpRequest, pk: int, slug: str = "", record: str | None = None
) -> HttpResponse:
    """Draw one page for this viewer."""
    page = visible_page(request, pk)

    if "reset" in request.GET:
        remember_filters(page, request.user, {})
        return redirect(page.get_absolute_url())

    if page.page_type == PageType.CUSTOM_TEMPLATE and page.template_name:
        return render(request, page.template_name, {"page": page})

    row = bound_record(page, request, record)
    if page.page_type == PageType.DETAIL and row is None:
        raise Http404("a detail page needs a record")

    tab = request.GET.get("tab", "")
    sets = saved_filter_sets(page, request.user)
    chosen = chosen_set(page, request, sets)

    # Choosing a set is the more deliberate act, so it wins over whatever the
    # controls were showing when it was chosen.
    submitted = dict(chosen.values) if chosen else submitted_filters(request, page)
    if submitted is not None:
        remember_filters(page, request.user, submitted)
    values = submitted if submitted is not None else default_filters(page, request.user)

    template = (
        "plinta/pages/detail.html"
        if page.page_type == PageType.DETAIL
        else "plinta/pages/page.html"
    )
    return render(
        request,
        template,
        {
            "page": page,
            "tab": tab,
            "record": row,
            "capabilities": capability_sections(row, request.user),
            "placements": render_page(
                page,
                request.user,
                tab=tab,
                filters=values,
                query=request.GET,
                record=row,
            ),
            "filter_values": values,
            "filter_controls": drawn_controls(page, values, request.user),
            "filter_sets": sets,
            "chosen_set": chosen,
            # Whether the bar offers to save what is on screen. The permission
            # decides the control; the pipeline decides the save.
            "may_save_filters": request.user.has_perm("plinta_pages.add_filterset"),
        },
    )


def capability_sections(record, user) -> list:
    """What each installed app contributes to this record's page.

    Empty when there is no record and when nothing is installed, so a
    dashboard draws none and an installation with no contrib app draws none.
    """
    from plinta.blocks.capabilities import for_object

    if record is None:
        return []
    return for_object(record, user=user)

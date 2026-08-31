"""The views the shell serves: a page, and nothing else yet.

A page is resolved by **id**; the slug in the URL is decorative and is not
checked, so renaming a page does not break a link someone shared (§9.0).
"""
from __future__ import annotations

from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render

from plinta.pages.models import Page, PageType
from plinta.pages.rendering import (
    drawn_controls,
    controls_of,
    default_filters,
    remember_filters,
    render_page,
    saved_filter_sets,
)
from plinta.permissions import can

#: Query parameters the filter bar uses for itself.
RESERVED = {"tab", "page", "sort", "reset", "view", "filterset"}


def submitted_filters(request: HttpRequest, page: Page) -> dict[str, Any] | None:
    """The filter values in the query string, or None if it carries none.

    Only fields the page declares are read. A query string naming anything
    else is ignored, because the bar is what the page exposes and a URL is
    not (§9.4).

    A control whose widget takes several values is read with `getlist`; every
    other with `get`. An empty selection reaches here as an empty list, which
    `filter_q` drops — so clearing a multi-select clears the filter
    rather than reapplying the default.
    """
    from plinta.pages.widgets import find

    declared = {control.field_name: control for control in controls_of(page)}
    sent: dict[str, Any] = {}
    for name in request.GET:
        if name in RESERVED or name not in declared:
            continue
        widget = find(declared[name].widget)
        if widget is not None and widget.bounds:
            continue  # read below, from its two keys rather than from this one
        if widget is not None and widget.multiple:
            # `GET[name]` keeps only the last of a repeated key, so a
            # multi-valued control would silently filter on whichever option
            # happened to be last in the form.
            sent[name] = [v for v in request.GET.getlist(name) if v != ""]
        else:
            sent[name] = request.GET[name]

        # A control offering a choice of operator submits it as its own key,
        # `<field>__op`. The **path** is never assembled from input: only
        # which operator, and only from what this control offers.
        control = declared[name]
        if control.allowed_lookups:
            asked = request.GET.get(f"{name}__op", "")
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
            edge: request.GET.get(f"{name}__{edge}", "").strip()
            for edge in ("from", "to")
        }
        if any(bounds.values()):
            sent[name] = {k: v for k, v in bounds.items() if v}
        elif f"{name}__from" in request.GET or f"{name}__to" in request.GET:
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

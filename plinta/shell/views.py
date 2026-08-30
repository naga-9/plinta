"""The views the shell serves: a page, and nothing else yet.

A page is resolved by **id**; the slug in the URL is decorative and is not
checked, so renaming a page does not break a link someone shared (§9.0).
"""
from __future__ import annotations

from typing import Any

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from plinta.pages.models import Page, PageType
from plinta.pages.rendering import (
    controls_of,
    default_filters,
    remember_filters,
    render_page,
    saved_filter_sets,
)
from plinta.permissions import can

#: Query parameters the filter bar uses for itself.
RESERVED = {"tab", "page", "sort", "reset", "view"}


def submitted_filters(request: HttpRequest, page: Page) -> dict[str, Any] | None:
    """The filter values in the query string, or None if it carries none.

    Only fields the page declares are read. A query string naming anything
    else is ignored, because the bar is what the page exposes and a URL is
    not (§9.4).
    """
    declared = {control.field_name for control in controls_of(page)}
    sent = {
        name: value
        for name, value in request.GET.items()
        if name in declared and name not in RESERVED
    }
    return sent or None


def page_view(request: HttpRequest, pk: int, slug: str = "") -> HttpResponse:
    """Draw one page for this viewer.

    A page the viewer may not see is a 404 rather than a 403: telling someone
    a page exists but is not theirs is itself a disclosure.
    """
    try:
        page = Page.objects.select_related("primary_data_source").get(pk=pk)
    except Page.DoesNotExist as exc:
        raise Http404("no such page") from exc

    if not page.is_active or not can(request.user, "view", page):
        raise Http404("no such page")

    if "reset" in request.GET:
        remember_filters(page, request.user, {})
        return redirect(page.get_absolute_url())

    if page.page_type == PageType.CUSTOM_TEMPLATE and page.template_name:
        return render(request, page.template_name, {"page": page})

    tab = request.GET.get("tab", "")
    submitted = submitted_filters(request, page)
    if submitted is not None:
        remember_filters(page, request.user, submitted)
    values = submitted if submitted is not None else default_filters(page, request.user)

    return render(
        request,
        "plinta/pages/page.html",
        {
            "page": page,
            "tab": tab,
            "placements": render_page(
                page,
                request.user,
                tab=tab,
                filters=values,
                query=request.GET,
            ),
            "filter_values": values,
            "filter_sets": saved_filter_sets(page, request.user),
        },
    )

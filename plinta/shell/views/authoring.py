"""The authoring screens (§12): data sources, blocks, pages and their layout.

Ordinary permission-gated pages, not an admin. Each screen asks for the
model permission that makes it visible, then for the row it is about.
"""
from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from plinta.blocks.models import Block
from plinta.pages.models import Page
from plinta.permissions import can


def gated(request: HttpRequest, permission: str) -> None:
    """Refuse a screen to a viewer without ``permission`` — as a 404.

    A 404, not a 403: saying the screen exists but is not theirs is a
    disclosure, and an authoring screen is not something a viewer should
    learn the address of by being turned away from it.
    """
    if not request.user.has_perm(permission):
        raise Http404("no such page")


def reachable(user, action: str, queryset, pk) -> object:
    """The row ``pk`` names, if there is one and ``user`` may ``action`` it.

    `get_object_or_404` and the row policy in one step, and one answer for
    both misses: a row that exists and is not theirs is not found either,
    for the same reason `gated` says nothing.
    """
    row = get_object_or_404(queryset, pk=pk)
    if not can(user, action, row):
        raise Http404(f"no such {row._meta.model_name}")
    return row


@login_required
def data_sources(request: HttpRequest) -> HttpResponse:
    """Every model plinta may draw, and a form to register another.

    Permission-gated like any screen, with no separate admin concept: holding
    `view_datasource` is what makes this visible, and `add_datasource` is what
    makes the form appear.
    """
    from plinta.datasources.models import DataSource
    from plinta.shell.authoring import DataSourceForm

    gated(request, "plinta_datasources.view_datasource")

    may_add = request.user.has_perm("plinta_datasources.add_datasource")
    form = DataSourceForm(request.POST or None) if may_add else None
    if request.method == "POST" and form is not None and form.is_valid():
        created = form.save()
        return redirect(f"/data-sources/{created.pk}/")

    return render(
        request,
        "plinta/authoring/data_sources.html",
        {
            "sources": DataSource.objects.select_related("content_type")
            .order_by("label"),
            "form": form,
            "may_add": may_add,
        },
    )


@login_required
def data_source(request: HttpRequest, pk: int) -> HttpResponse:
    """One model's columns.

    Saving here is what mints, renames and removes field permissions — the
    signals on `DataSourceField` do it — so this screen is the entry point for
    the permission surface as well as the column surface (§5.7).
    """
    from plinta.datasources.models import DataSource, DataSourceField
    from plinta.shell.authoring import (
        ColumnFormSet,
        DataSourceForm,
        field_paths,
        split,
    )

    gated(request, "plinta_datasources.view_datasource")
    source = get_object_or_404(
        DataSource.objects.select_related("content_type"), pk=pk
    )
    may_change = request.user.has_perm("plinta_datasources.change_datasource")
    columns = DataSourceField.objects.filter(data_source=source).order_by(
        "order", "pk"
    )

    details = DataSourceForm(
        request.POST if request.POST.get("what") == "source" else None,
        instance=source,
    )
    formset = ColumnFormSet(
        request.POST if request.POST.get("what") == "columns" else None,
        queryset=columns,
    )

    if request.method == "POST" and may_change:
        if request.POST.get("what") == "source" and details.is_valid():
            details.save()
            return redirect(f"/data-sources/{pk}/")
        if request.POST.get("what") == "columns" and formset.is_valid():
            for column in formset.save(commit=False):
                column.data_source = source
                column.save()
            for column in formset.deleted_objects:
                column.delete()
            return redirect(f"/data-sources/{pk}/")

    return render(
        request,
        "plinta/authoring/data_source.html",
        {
            "source": source,
            "details": details,
            "formset": formset,
            "rows": split(formset),
            "paths": field_paths(source.model),
            "may_change": may_change,
        },
    )


@login_required
def blocks(request: HttpRequest) -> HttpResponse:
    """Every block this viewer may see, and the three things you do to one.

    Create, duplicate, delete. Sharing is the inspector's, because it is a
    decision about one block rather than a bulk action.
    """
    from plinta.blocks.inspector import duplicate, visible_blocks
    from plinta.shell.authoring import BlockCreateForm

    # `change_block`, not `view_block`: every signed-in person needs the
    # latter for a dashboard to draw at all, so gating on it would show an
    # authoring screen to everybody. Reaching this screen is authoring.
    gated(request, "plinta_blocks.change_block")

    may_add = request.user.has_perm("plinta_blocks.add_block")
    form = BlockCreateForm(request.POST or None) if may_add else None

    if request.method == "POST":
        action = request.POST.get("action") or "create"
        if action in {"duplicate", "delete"}:
            block = reachable(
                request.user, "view", Block, request.POST.get("block") or 0
            )
            if action == "duplicate" and may_add:
                return redirect(f"/blocks/{duplicate(block, request.user).pk}/")
            if action == "delete" and can(request.user, "delete", block):
                block.delete()
            return redirect("/blocks/")
        if form is not None and form.is_valid():
            created = form.save(commit=False)
            # Owned, not public. Publishing is a separate decision, made in
            # the inspector by somebody who can see what they are publishing.
            created.owner = request.user
            created.save()
            return redirect(f"/blocks/{created.pk}/")

    return render(
        request,
        "plinta/authoring/blocks.html",
        {
            "blocks": visible_blocks(request.user),
            "form": form,
            "may_add": may_add,
        },
    )


@login_required
def block_inspector(request: HttpRequest, pk: int) -> HttpResponse:
    """One block: its own fields, and its config derived from the schema.

    Two forms, told apart by a hidden `what`, for the reason the Data Sources
    screen has two: renaming a block and rearranging its settings are
    different intentions, and one failing should not discard the other.
    """
    from plinta.blocks.inspector import save_config, settings_for
    from plinta.components.registry import find
    from plinta.forms.layouts import layout_for
    from plinta.shell.authoring import BlockForm

    gated(request, "plinta_blocks.change_block")
    block = reachable(
        request.user, "view", Block.objects.select_related("data_source"), pk
    )
    may_change = can(request.user, "change", block)
    component = find(block.component_type)

    what = request.POST.get("what") if request.method == "POST" else None
    details = BlockForm(request.POST if what == "block" else None, instance=block)
    errors: dict = {}

    if request.method == "POST" and may_change:
        if what == "block":
            if details.is_valid():
                saved = details.save(commit=False)
                # `owner = None` is public, the same one field a saved view
                # publishes through (§6.1b).
                saved.owner = None if request.POST.get("public") else request.user
                saved.save()
                return redirect(f"/blocks/{pk}/")
        elif what == "config":
            errors = save_config(block, request.user, request.POST)
            if not errors:
                return redirect(f"/blocks/{pk}/")

    settings = settings_for(component, block, request.user) if component else []
    return render(
        request,
        "plinta/authoring/block.html",
        {
            "block": block,
            "component": component,
            "details": details,
            "settings": settings,
            "settings_by_name": {s["name"]: s for s in settings},
            "layout": layout_for(component.config_schema) if component else "",
            "may_change": may_change,
            # Flattened: a template cannot read the `_general` key, and the
            # derived controls have nowhere to hang a per-field message yet.
            "errors": [
                message if name == "_general" else f"{name}: {message}"
                for name, messages in errors.items()
                for message in messages
            ],
        },
    )


@login_required
def pages(request: HttpRequest) -> HttpResponse:
    """Every page this viewer may compose, and a form to start another."""
    from plinta.permissions import allowed
    from plinta.shell.authoring import PageForm

    gated(request, "plinta_pages.change_page")

    may_add = request.user.has_perm("plinta_pages.add_page")
    form = PageForm(request.POST or None) if may_add else None
    if request.method == "POST" and form is not None and form.is_valid():
        created = form.save(commit=False)
        created.owner = request.user
        created.save()
        return redirect(f"/pages/{created.pk}/compose/")

    return render(
        request,
        "plinta/authoring/pages.html",
        {
            "pages": allowed(request.user, "view", Page.objects.all()),
            "form": form,
            "may_add": may_add,
        },
    )


@login_required
def page_composer(request: HttpRequest, pk: int) -> HttpResponse:
    """One page: its settings, the blocks on it, and where each one sits.

    The grid is a form of plain numbers. The page's own *Edit layout* makes
    the same four integers draggable and posts them to the same rule
    (§12.4); this is the precise-adjust path.
    """
    from plinta.pages.composition import (
        CompositionError,
        placed,
        positions,
        submitted_positions,
    )
    from plinta.shell.authoring import PageForm, PlacementForm

    gated(request, "plinta_pages.change_page")
    page = reachable(request.user, "view", Page, pk)
    may_change = can(request.user, "change", page)

    what = request.POST.get("what") if request.method == "POST" else None
    settings_form = PageForm(request.POST if what == "page" else None, instance=page)
    placement_form = PlacementForm(
        request.POST if what == "place" else None, page=page, user=request.user
    )

    if request.method == "POST" and may_change:
        if what == "page" and settings_form.is_valid():
            settings_form.save()
            return redirect(f"/pages/{pk}/compose/")
        if what == "place" and placement_form.is_valid():
            placement = placement_form.save(commit=False)
            placement.page = page
            # Beneath whatever is there, full width. A block that lands on top
            # of another is a page somebody has to repair before reading.
            placement.row = max(
                (p.row + p.height for p in page.placements.all()), default=0
            )
            placement.column, placement.width = 0, 12
            placement.save()
            return redirect(f"/pages/{pk}/compose/")
        if what == "remove":
            page.placements.filter(pk=request.POST.get("placement") or 0).delete()
            return redirect(f"/pages/{pk}/compose/")
        if what == "positions":
            try:
                positions(page, request.user, submitted_positions(request.POST))
            except CompositionError as exc:
                raise Http404("no such page") from exc
            return redirect(f"/pages/{pk}/compose/")

    return render(
        request,
        "plinta/authoring/page.html",
        {
            "subject": page,
            "settings_form": settings_form,
            "placement_form": placement_form,
            "placements": placed(page, request.user),
            "may_change": may_change,
        },
    )


@require_POST
@login_required
def page_positions(request: HttpRequest, pk: int) -> JsonResponse:
    """Persist a drag. The endpoint the layout editor posts to.

    JSON rather than form fields, because a drag has no reason to speak in
    them — but the same rule, so an enhancement cannot move a block its
    viewer could not move by typing.
    """
    from plinta.pages.composition import CompositionError, positions

    page = reachable(request.user, "view", Page, pk)
    try:
        wanted = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "unreadable"}, status=400)
    if not isinstance(wanted, dict):
        return JsonResponse({"error": "unreadable"}, status=400)

    try:
        moved = positions(page, request.user, wanted)
    except CompositionError as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    return JsonResponse({"moved": [placement.pk for placement in moved]})

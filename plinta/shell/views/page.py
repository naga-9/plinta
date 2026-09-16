"""A page, and what surrounds it: its filters, its saved filter sets, home.

Also the helpers the other two files share — which page a request may see,
what its filter bar submitted, and what Unpoly said about the request.
"""
from __future__ import annotations

import json
import re
from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render

from plinta.pages.actions import visible_actions
from plinta.pages.models import Page, PageType
from plinta.pages.rendering import (
    controls_of,
    default_filters,
    drawn_controls,
    remember_filters,
    render_page,
    saved_filter_sets,
)
from plinta.permissions import can
from plinta.shell.views.returning import back_to

#: Query parameters the filter bar uses for itself.
RESERVED = {"tab", "page", "sort", "reset", "view", "filterset", "next"}

#: One card's id, as the fragment swap addresses it (`pages/block.html`).
CARD = re.compile(r"^#card-(\d+)$")

#: What a filter change swaps: the grid, and the bar and the saved-set picker
#: where the page has them. The rest of the screen stays where it was.
FILTER_TARGETS = "#pl-grid, #pl-filters:maybe, #pl-filter-sets:maybe"


def closes_a_layer(request: HttpRequest) -> bool:
    """Whether this page was asked for by something inside an overlay.

    Unpoly says which layer a request is for in ``X-Up-Mode``. A page is
    never drawn inside an overlay: the form that was — a view editor, a
    filter-set editor — has posted and been redirected here, and what it
    means is "done". So the page answers with `X-Up-Accept-Layer`, which
    closes the overlay, and whoever opened it decides what to redraw from
    the response. No URL pattern on the opener, which a mounting prefix or a
    detail page would have broken.
    """
    return request.headers.get("X-Up-Mode", "root") != "root"


def cards_asked_for(request: HttpRequest) -> set[int] | None:
    """The placements a fragment request will keep, or None for all of them.

    Unpoly names what it is about to swap in ``X-Up-Target``. When that is
    one card, or several, the rest of the page is rendered for nobody — so
    the view draws those alone. Anything else in the list, or no header at
    all, is the whole page.
    """
    header = request.headers.get("X-Up-Target", "")
    if not header:
        return None
    found = set()
    for selector in header.split(","):
        match = CARD.match(selector.strip())
        if match is None:
            return None
        found.add(int(match.group(1)))
    return found or None


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

    From the path — `/pages/<id>-<slug>/<record>/` — and nowhere else: the URL
    is the thing somebody sends a colleague, so it is the one place the
    record lives.

    Raises:
        Http404: the page names no model, the row does not exist, or the
            viewer may not see it. A 404 rather than a 403 throughout: saying
            a record exists but is not yours is itself a disclosure.
    """
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

    page = visible_page(request, pk)
    mine = filter_sets.visible_sets(page, request.user)

    if request.method == "POST":
        return _save_filter_set(request, page, mine)

    chosen = next(
        (s for s in mine if str(s.pk) == (request.GET.get("set") or "")), None
    )
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
        _filter_set_editor(request, page, mine, chosen, values),
    )


def _filter_set_editor(request, page, mine, filter_set, values, errors=None) -> dict:
    """What the editor draws, opened on ``filter_set`` with ``values`` in its
    controls — fresh, or again with ``errors`` after a post. One place, so
    the two cannot drift."""
    from plinta.pages import filter_sets

    return {
        "page": page,
        "sets": mine,
        "set": filter_set,
        "filter_controls": drawn_controls(page, values, request.user),
        "may_publish": filter_sets.may_publish(request.user),
        "may_default": filter_sets.may_default(request.user),
        "may_delete": filter_set is not None
        and can(request.user, "delete", filter_set),
        "action": request.path,
        # Where the layer was opened over, to go back to (`back_to`).
        "next": request.POST.get("next") or request.GET.get("next") or "",
        "errors": errors or {},
    }


def _save_filter_set(request: HttpRequest, page, mine):
    """Create, update or delete one set, then send the viewer back to it."""
    from django.core.exceptions import ValidationError

    from plinta.blocks.write import WriteDenied
    from plinta.pages import filter_sets

    asked = request.POST.get("set") or ""
    existing = next((s for s in mine if str(s.pk) == asked), None)

    if request.POST.get("action") == "delete":
        if existing is None or not can(request.user, "delete", existing):
            raise Http404("no such filter set")
        existing.delete()
        return redirect(back_to(request, page.get_absolute_url()))

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
            _filter_set_editor(
                request, page, mine, existing,
                submitted_filters(request, page, request.POST) or {},
                exc.message_dict,
            ),
            status=422,
        )

    return redirect(back_to(request, page.get_absolute_url(), filterset=saved.pk))


@login_required
def home(request: HttpRequest) -> HttpResponse:
    """Where signing in lands.

    The shell's, not a `Page` row (§13.1): it lists whatever the viewer may
    open, so it cannot itself be one of the things being listed. Built from
    the same menu the sidebar draws, which is already permission-filtered — so
    this screen has no access rule of its own and cannot disagree with the
    navigation beside it.
    """
    from plinta.shell.menu import build

    return render(
        request,
        "plinta/shell/home.html",
        {"sections": build(request.user)},
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

    # The bar asking, as a control is chosen, what the others should now
    # offer — the cascade. Nothing has been applied: the choice is not
    # remembered, and no card is drawn for a request that keeps the bar
    # alone. Applying first to find out what to apply is the wrong order.
    asking = bool(request.headers.get("X-Up-Validate"))

    # Choosing a set is the more deliberate act, so it wins over whatever the
    # controls were showing when it was chosen.
    submitted = dict(chosen.values) if chosen else submitted_filters(request, page)
    if submitted is not None and not asking:
        remember_filters(page, request.user, submitted)
    values = submitted if submitted is not None else default_filters(page, request.user)

    template = (
        "plinta/pages/detail.html"
        if page.page_type == PageType.DETAIL
        else "plinta/pages/page.html"
    )
    response = render(
        request,
        template,
        {
            "page": page,
            "tab": tab,
            "record": row,
            "capabilities": capability_sections(row, request.user),
            "placements": [] if asking else render_page(
                page,
                request.user,
                tab=tab,
                filters=values,
                query=request.GET,
                record=row,
                only=cards_asked_for(request),
            ),
            "filter_values": values,
            "filter_controls": drawn_controls(page, values, request.user),
            "filter_sets": sets,
            "chosen_set": chosen,
            "filter_targets": FILTER_TARGETS,
            # Whether the bar offers to save what is on screen. The permission
            # decides the control; the pipeline decides the save.
            "may_save_filters": request.user.has_perm("plinta_pages.add_filterset"),
            # Whatever an app puts in this page's header (§12.4). Core names
            # no package; it draws what is registered.
            "page_actions": visible_actions(page, request.user),
        },
    )
    if closes_a_layer(request):
        response["X-Up-Accept-Layer"] = json.dumps(
            {"location": request.get_full_path()}
        )
    return response


def capability_sections(record, user) -> list:
    """What each installed app contributes to this record's page.

    Empty when there is no record and when nothing is installed, so a
    dashboard draws none and an installation with no contrib app draws none.
    """
    from plinta.blocks.capabilities import for_object

    if record is None:
        return []
    return for_object(record, user=user)

"""Composing a page: which placements a viewer gets, and with what filters.

Two degradations, both normal states rather than errors: a placed block the
viewer may not see, and one whose component is not installed. Making a block
private, or uninstalling a component, must never break the page holding it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db.models import Q

from plinta.pages.models import (
    FilterSet,
    Page,
    PageBlock,
    PageFilter,
    PageFilterPreference,
    Widget,
)


@dataclass(frozen=True)
class Placement:
    """One block drawn on a page, with the grid position it occupies."""

    placement: PageBlock
    html: str
    column: int
    row: int
    width: int
    height: int
    #: Set when the block could not be drawn. The card shows this instead.
    error: str = ""
    #: How much room the card gives the component's markup (§7.2).
    padding: str = "default"
    #: The saved views the viewer may pick between, and the one in force.
    views: list = field(default_factory=list)
    view: Any = None
    #: What the card's header offers to do with this block.
    actions: list = field(default_factory=list)
    #: Where the card opens a record's form. An action reads it from here
    #: rather than building a URL, which is the page's job (§9.0).
    form_url: str = ""

    @property
    def param(self) -> str:
        """This placement's query-string prefix — `b3_` for placement 3.

        Two tables on one page sort, page and choose views independently, so
        every parameter a block owns carries it.
        """
        return f"b{self.placement.pk}_"

    @property
    def title(self) -> str:
        """The placement's own title, or the block's name."""
        return self.placement.title or self.placement.block.name

    @property
    def is_empty(self) -> bool:
        """Whether this drew nothing — an empty slot."""
        return not self.html and not self.error


def placements_for(page: Page, user, *, tab: str = "") -> list[PageBlock]:
    """The placements to draw, in order.

    Filtered by the placement's own visibility and its tab. Whether the viewer
    may see the *block* is decided when it renders, because an unviewable block
    is an empty slot rather than a missing one — the grid keeps its shape.
    """
    # The content type is joined because every block resolves its model
    # through it, which would otherwise be a query per placement.
    placements = page.placements.filter(is_visible=True).select_related(
        "block", "block__data_source", "block__data_source__content_type"
    )
    if tab:
        placements = placements.filter(tab__in=["", tab])
    return list(placements)


def controls_of(page: Page) -> list[PageFilter]:
    """The page's filter controls, read once per page instance.

    Both the default-value lookup and the keyword building need them, and a
    page is rendered once, so the second read is a round trip for nothing.
    """
    if not hasattr(page, "_plinta_controls"):
        page._plinta_controls = list(page.filters.all())
    return page._plinta_controls


def default_filters(page: Page, user) -> dict[str, Any]:
    """The filter values to start from, when the viewer sent none.

    Their remembered state first, then their own default set, then a public
    one, then each filter's own default. Every step is something someone
    marked; nothing is picked by accident.
    """
    from plinta.permissions import allowed

    if user is not None and getattr(user, "is_authenticated", False):
        remembered = PageFilterPreference.objects.filter(page=page, owner=user).first()
        if remembered and remembered.values:
            return dict(remembered.values)

        sets = allowed(user, "view", page.filter_sets.filter(is_default=True))
        chosen = (
            sets.filter(owner=user).first() or sets.filter(owner__isnull=True).first()
        )
        if chosen:
            return dict(chosen.values)

    return {
        f.field_name: f.default_value
        for f in controls_of(page)
        if f.default_value is not None
    }


def resolve_filters(values: dict[str, Any], user, record: Any = None) -> dict[str, Any]:
    """Filter values with their placeholders resolved for this viewer.

    A token nothing registered is left as written, so it matches nothing rather
    than widening the filter it was written to narrow.

    ``record`` is the row a detail page is about, which is what `__RECORD__`
    resolves to.
    """
    from plinta.utils.placeholders import Context, resolve_values

    return resolve_values(values or {}, Context(user=user, record=record))


#: What a yes/no control may send. A query string carries strings, and a
#: `BooleanField` accepts "True" and "1" but not "true" — which is what the
#: bar draws, and what a remembered filter therefore stores.
TRUTHY = frozenset({"true", "1", "yes", "on", "t"})
FALSEY = frozenset({"false", "0", "no", "off", "f"})


def coerce(control: PageFilter, value: Any) -> Any:
    """One control's value as the ORM wants it, or None to drop it.

    Only booleans need this. Django coerces a string to a number, a date or a
    UUID on its own, but `BooleanField.to_python` rejects anything outside
    "True"/"False"/"1"/"0" — so a control that draws `true` raises
    `ValidationError` from inside the query rather than filtering.

    A value that is neither is dropped rather than raising: it can only come
    from a hand-edited URL, and a page that 500s on a stray parameter is worse
    than one that ignores it.
    """
    if control.widget != Widget.BOOLEAN:
        return value
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in TRUTHY:
        return True
    if text in FALSEY:
        return False
    return None


@dataclass(frozen=True)
class DrawnControl:
    """One filter control, ready for its widget's template.

    Assembled in the view rather than in the template, so the option query
    happens once per control and a template cannot decide to run one.
    """

    control: Any
    template: str
    value: Any = ""
    options: list = field(default_factory=list)
    truncated: bool = False
    #: What the operator picker offers. Empty means no picker.
    lookups: list = field(default_factory=list)
    #: Which of them is in force.
    lookup: str = ""

    @property
    def control_id(self) -> str:
        return f"pl-filter-{self.control.pk}"


def drawn_controls(page: Page, values: dict[str, Any], user) -> list[DrawnControl]:
    """Every control on ``page``, with what its widget needs to draw it.

    A widget nothing registered falls back to a text input: a filter naming an
    uninstalled one still narrows, which is the same degradation a block with
    an unregistered component makes.
    """
    from plinta.pages.options import CAP, options_for
    from plinta.pages.widgets import find

    drawn = []
    for control in controls_of(page):
        widget = find(control.widget) or find(Widget.INPUT)
        options = []
        if widget and widget.needs_ranges:
            # Registered windows, not values from the data: no row contains
            # "current month" (§3.2).
            from plinta.dates.ranges import registered

            options = [(r.name, r.label) for r in registered()]
        elif widget and widget.needs_options:
            # The cascade: every control's selection except this one's. A
            # control that narrowed itself would drop the alternatives from
            # its own list, and the choice could not then be changed.
            siblings = {
                name: value
                for name, value in (values or {}).items()
                if name != control.field_name
            }
            options = options_for(
                control, user, siblings=filter_q(page, siblings, user)
            )
        value = values.get(control.field_name)
        lookups = control.offered_lookups()
        chosen = control.lookup
        if lookups and isinstance(value, dict):
            chosen, value = chosen_lookup(control, value)
        if widget and widget.bounds:
            value = value if isinstance(value, dict) else {}
        elif widget and widget.multiple:
            # A list of strings, because the options are strings: a stored
            # default of `[3]` would otherwise never match option `"3"`, and
            # `in` on a bare string is a substring test that ticks "2" for a
            # value of "12".
            value = [str(v) for v in value] if isinstance(value, list) else (
                [str(value)] if value not in (None, "") else []
            )
        drawn.append(
            DrawnControl(
                control=control,
                template=widget.template if widget else "plinta/filters/input.html",
                value=value if value is not None else "",
                options=options,
                truncated=len(options) >= CAP,
                lookups=lookups,
                lookup=chosen,
            )
        )
    return drawn


def control_q(control: PageFilter, value: Any, widget) -> Q | None:
    """One control's contribution to the query, or None for "no filter".

    A `Q` rather than keyword arguments, because two of the shapes cannot be
    expressed as `{field: value}`: a range is **two** keys from one control,
    and a relative range is a disjunction — "past or this month" is one choice
    and two conditions.

    The lookup comes from the widget's declared shape, never from the query
    string. A viewer who could name their own would have `__regex` for a
    denial of service and `owner__password__startswith` for a search.
    """
    if value is None or value == "" or value == []:
        return None

    if widget is not None and widget.bounds:
        # `{"from": ..., "to": ...}`, and either half alone is a valid filter:
        # "anything after March" is a question people ask.
        start, end = (value or {}).get("from"), (value or {}).get("to")
        bounds = {}
        if start:
            bounds[f"{control.field_name}__gte"] = start
        if end:
            bounds[f"{control.field_name}__lte"] = end
        return Q(**bounds) if bounds else None

    if widget is not None and widget.needs_ranges:
        from plinta.dates.ranges import resolve_q

        # Several names OR together, which is why this cannot be kwargs.
        return resolve_q(control.field_name, value)

    lookup, value = chosen_lookup(control, value)
    if value is None or value == "" or value == []:
        return None
    suffix = "" if lookup == "exact" else f"__{lookup}"
    return Q(**{f"{control.field_name}{suffix}": value})


def chosen_lookup(control: PageFilter, value: Any) -> tuple[str, Any]:
    """The operator to filter with, and the value to filter on.

    The second of two gates. `PageFilter.clean` refuses a stored operator
    plinta does not know; this refuses a **submitted** one the control does
    not offer, falling back to the author's own. An operator that reached the
    query is one somebody chose from a list, never one they wrote.
    """
    if not isinstance(value, dict) or "op" not in value:
        return control.lookup, value
    asked = value.get("op")
    offered = control.allowed_lookups or []
    return (asked if asked in offered else control.lookup), value.get("value")


def filter_q(page: Page, values: dict[str, Any], user, record: Any = None) -> Q:
    """The stored values as one `Q`, ANDed across the controls.

    A value for a field the page does not declare is ignored: the bar is what
    the page exposes, and the query string is not.
    """
    from plinta.pages.widgets import find

    resolved = resolve_filters(values, user, record)
    combined = Q()
    for control in controls_of(page):
        widget = find(control.widget)
        part = control_q(control, coerce(control, resolved.get(control.field_name)), widget)
        if part is not None:
            combined &= part
    return combined


def _param(query: Any, name: str) -> str:
    """One value from the request's query string, or empty."""
    if query is None:
        return ""
    try:
        return query.get(name, "") or ""
    except AttributeError:
        return ""


def render_page(
    page: Page,
    user,
    *,
    tab: str = "",
    filters: dict[str, Any] | None = None,
    query: Any = None,
    record: Any = None,
) -> list[Placement]:
    """Draw every placement on ``page`` for ``user``.

    Returns one `Placement` per slot, including the empty ones, so the grid
    keeps its shape when a block is hidden or its component is uninstalled.

    ``record`` is the row a detail page is about. It reaches a placement
    through its ``context_filter``, where `__RECORD__` resolves to the row's
    primary key — so one placement serves every record the page shows.

    ``query`` is the request's query string, handed to each block so it can
    build its own sort and page links. Each placement's parameters are
    prefixed with its id, so two tables on one page sort independently rather
    than moving together.
    """
    from plinta.blocks.rendering import BlockRenderError, render_block

    values = default_filters(page, user) if filters is None else filters
    narrowing = filter_q(page, values, user, record)

    from plinta.blocks.actions import actions_for
    from plinta.blocks.rendering import chosen_view, views_for
    from plinta.components.registry import find as find_component

    slots = placements_for(page, user, tab=tab)
    # One query for every block on the page, before the loop: asking inside it
    # would make each extra block cost more than the last.
    by_block = views_for([slot.block for slot in slots], user)

    drawn = []
    for placement in slots:
        html, error = "", ""
        prefix = f"b{placement.pk}_"
        views = by_block.get(placement.block_id, [])
        # The view the viewer picked, or the one that applies. Passed through,
        # without which a non-default view is unreachable however it is
        # offered.
        view = chosen_view(
            views,
            user,
            _param(query, f"{prefix}view"),
            placement_default=placement.default_view_id,
        )
        try:
            html = render_block(
                placement.block,
                user,
                view=view,
                extra_filters=narrowing
                & Q(**resolve_filters(placement.context_filter, user, record)),
                query=query,
                param_prefix=prefix,
                # Only the page knows which placement this is, and the feed is
                # placement-scoped — so the URL is handed to the component
                # rather than built by it.
                data_url=f"/pages/{page.pk}/blocks/{placement.pk}/data/",
                # The write half of the same conversation. Handed over
                # unconditionally; a component that cannot write ignores it,
                # and the endpoint refuses one in its name anyway.
                write_url=f"/pages/{page.pk}/blocks/{placement.pk}/write/",
                options_url=f"/pages/{page.pk}/blocks/{placement.pk}/options/",
                form_url=f"/pages/{page.pk}/blocks/{placement.pk}/form/",
                # The row a detail page is about. A component that edits one
                # needs to know which; everything else ignores it.
                record=record,
                page=_page_number(query, prefix),
                sort=_sort_param(query, prefix),
            )
        except BlockRenderError as exc:
            # The block says so in its own slot; the other seven still draw.
            error = str(exc)
        component = find_component(placement.block.component_type)
        drawn.append(
            Placement(
                placement=placement,
                html=html,
                error=error,
                padding=str(getattr(component, "padding", "default")),
                views=views,
                view=view,
                actions=actions_for(placement.block, user, views=views),
                form_url=f"/pages/{page.pk}/blocks/{placement.pk}/form/",
                column=placement.column,
                row=placement.row,
                width=placement.width,
                height=placement.height,
            )
        )
    return drawn


def _page_number(query: Any, prefix: str) -> int:
    """Which page this placement is showing. Anything unusable is the first."""
    try:
        return max(1, int((query or {}).get(f"{prefix}page", 1)))
    except (TypeError, ValueError):
        return 1


def _sort_param(query: Any, prefix: str) -> str:
    """The column this placement is sorted by, ``-`` for descending."""
    return (query or {}).get(f"{prefix}sort", "") or ""


def remember_filters(page: Page, user, values: dict[str, Any]) -> None:
    """Store what this viewer last had the bar set to.

    Stored as written, placeholders included, so a saved ``__CURRENT_QUARTER__``
    keeps meaning the current quarter rather than freezing to one.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return
    PageFilterPreference.objects.update_or_create(
        page=page, owner=user, defaults={"values": values or {}}
    )


def saved_filter_sets(page: Page, user) -> list[FilterSet]:
    """The filter sets this viewer may choose from, in name order."""
    from plinta.permissions import allowed

    return list(allowed(user, "view", page.filter_sets.all()))

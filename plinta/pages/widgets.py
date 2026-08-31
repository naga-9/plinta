"""How a filter control is drawn, and what it can carry.

A registry rather than an enum on the model, for the reason every other
registry here exists: a closed set in core means a third party cannot add to
it. `contrib.filters_tomselect` registers a multi-select that fetches its
options as you type; a consumer chooses it per filter by name, and core needs
no opinion about how large an option set may be.

Core registers five, and none of them is privileged — the same door
(§18.2 shape).

    register_filter_widget(
        "multiselect_tomselect",
        template="plinta/tomselect/multiselect.html",
        multiple=True,
        needs_options=True,
    )
"""
from __future__ import annotations

import re
from dataclasses import dataclass

NAME = re.compile(r"[a-z][a-z0-9_]*")


@dataclass(frozen=True)
class FilterWidget:
    """One way of drawing a filter control."""

    name: str
    label: str
    #: Rendered with the control, its current value, and its options.
    template: str
    #: Whether it submits several values. Decides `getlist` over `get`, and
    #: pairs with the `in` lookup.
    multiple: bool = False
    #: Whether it wants `options_for()` called. A text input does not, and
    #: calling it anyway would query for a list nothing draws.
    needs_options: bool = False


class WidgetError(Exception):
    """A widget was registered twice, named unusably, or asked for by a name
    nothing registered."""


_registry: dict[str, FilterWidget] = {}


def register_filter_widget(
    name: str,
    *,
    template: str,
    label: str = "",
    multiple: bool = False,
    needs_options: bool = False,
) -> FilterWidget:
    """Add a way of drawing a filter control.

    Raises:
        WidgetError: the name is taken, or is not lowercase
            ``[a-z][a-z0-9_]*``.
    """
    if not NAME.fullmatch(name):
        raise WidgetError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in _registry:
        raise WidgetError(f"{name!r} is already registered")
    widget = FilterWidget(
        name=name,
        label=label or name.replace("_", " ").title(),
        template=template,
        multiple=multiple,
        needs_options=needs_options,
    )
    _registry[name] = widget
    return widget


def registered() -> dict[str, FilterWidget]:
    """Every widget, by name. What a filter may choose from."""
    return dict(_registry)


def find(name: str) -> FilterWidget | None:
    """The widget called ``name``, or None if nothing registered it.

    None rather than raising, so a filter naming an uninstalled widget draws
    as a plain input rather than breaking the page — the same degradation a
    block with an unregistered component makes.
    """
    return _registry.get(name)


def get(name: str) -> FilterWidget:
    """The widget called ``name``.

    Raises:
        WidgetError: nothing is registered under it.
    """
    try:
        return _registry[name]
    except KeyError:
        known = ", ".join(sorted(_registry)) or "none"
        raise WidgetError(f"no filter widget named {name!r} (registered: {known})") from None


def register_defaults() -> None:
    """The five core draws. Called from `AppConfig.ready()`.

    `input` is the fallback for anything unregistered, so it is registered
    first and its template is the one a broken name lands on.
    """
    register_filter_widget(
        "input", template="plinta/filters/input.html", label="Text input"
    )
    register_filter_widget(
        "boolean", template="plinta/filters/boolean.html", label="Yes / no"
    )
    register_filter_widget(
        "select",
        template="plinta/filters/select.html",
        label="Select",
        needs_options=True,
    )
    register_filter_widget(
        "multiselect",
        template="plinta/filters/multiselect.html",
        label="Multi-select",
        multiple=True,
        needs_options=True,
    )
    register_filter_widget(
        "daterange", template="plinta/filters/daterange.html", label="Date range"
    )

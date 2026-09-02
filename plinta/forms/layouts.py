"""Where a component's settings are arranged, when stacked is not enough.

The split this exists for:

    **core owns the mechanisms** — a column chooser that knows which columns
    this viewer may see, a sort builder, a picker for a relation, and the
    rule that a blank control means "same as the block"

    **the component owns the arrangement** — which settings appear, in what
    order, under what headings

A chart, a gantt and a table have nothing in common but the mechanisms, and
core would guess the arrangement wrong for all three. So it does not guess:

    register_config_layout(ChartConfig, "yourapp/chart_settings.html")

    {# yourapp/chart_settings.html #}
    {% load plinta_form %}
    <div class="row">
      <div class="col-6">{% setting "x_field" %}</div>
      <div class="col-6">{% setting "y_field" %}</div>
    </div>
    <fieldset>
      <legend>Appearance</legend>
      {% setting "chart_type" %}
    </fieldset>

Registered against the **schema**, not a name, because a config form is always
about one schema and the schema is what the caller already has. It serves the
saved-view editor and the block inspector alike: the same settings, over a
delta in one and over the base in the other.
"""
from __future__ import annotations

from pydantic import BaseModel

#: Every setting, in declaration order, one after another. What a component
#: that registers nothing gets, and what most should keep.
DEFAULT = "plinta/settings/stacked.html"

_registry: dict[type[BaseModel], str] = {}


class LayoutError(Exception):
    """A layout could not be registered."""


def register_config_layout(schema: type[BaseModel], template: str) -> str:
    """Arrange ``schema``'s settings with ``template``.

    Raises:
        LayoutError: the schema already has one, or no template was named.
    """
    if not template:
        raise LayoutError(f"{schema.__name__} names no template")
    if schema in _registry:
        raise LayoutError(
            f"{schema.__name__} already has {_registry[schema]!r}"
        )
    _registry[schema] = template
    return template


def layout_for(schema: type[BaseModel]) -> str:
    """The template arranging ``schema``'s settings, or the stacked default.

    Walked up the MRO so a base schema's arrangement reaches its subclasses —
    the same rule widget overrides follow, and for the same reason: a setting
    declared on a base is the same setting on every subclass.
    """
    for cls in getattr(schema, "__mro__", ()):
        if cls in _registry:
            return _registry[cls]
    return DEFAULT


def registered() -> list[str]:
    return sorted(schema.__name__ for schema in _registry)

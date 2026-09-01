"""`{% control %}` — draw one of a form's fields where the layout wants it."""
from __future__ import annotations

from django import template
from django.template.loader import render_to_string
from django.utils.safestring import SafeString

register = template.Library()


@register.simple_tag(takes_context=True)
def control(context, name: str) -> SafeString:
    """One control by field name.

    Draws nothing when the form has no such field, which is the ordinary case
    rather than an error: a layout is written once and the fields it places
    depend on the viewer, so a reader without the change permission for one
    of them simply gets a form without it.
    """
    drawn = (context.get("controls_by_name") or {}).get(name)
    if drawn is None:
        return SafeString("")
    return SafeString(
        render_to_string(
            "plinta/components/control.html",
            {"control": drawn, "cls": context.get("cls") or {}},
        )
    )

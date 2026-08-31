"""Template helpers. All five are generic; none knows a domain."""
from __future__ import annotations

import datetime
import json
from typing import Any

from django import template
from django.conf import settings

register = template.Library()

#: The three characters that could break out of a `<script>` tag, escaped as
#: JSON's own unicode sequences. The same set `django.utils.html.json_script`
#: uses, applied here because this filter also feeds data attributes.
SCRIPT_ESCAPES = {ord(">"): "\\u003E", ord("<"): "\\u003C", ord("&"): "\\u0026"}


@register.simple_tag
def site_name() -> str:
    """The installation's name, for a template rendered without a request.

    An email has no request and so no context processor. Request-rendered
    templates read ``site_name`` from `branding` instead.
    """
    return getattr(settings, "PLINTA_SITE_NAME", "plinta")


@register.filter
def get_item(container: Any, key: Any) -> Any:
    """One value out of a dict, or an attribute off an object.

    Django's template language cannot index by a variable key, which is what
    every table cell needs.
    """
    if container is None:
        return None
    if isinstance(container, dict):
        return container.get(key)
    return getattr(container, key, None)


@register.filter
def classify_value(value: Any) -> str:
    """Which branch of a recursive template should draw this value.

    A config inspector walks arbitrary JSON, and a template cannot ask what
    type something is. The names are render branches, not Python types:
    ``empty`` covers None and the empty string, because both draw the same.
    """
    if value is None or value == "":
        return "empty"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "mapping"
    if isinstance(value, (list, tuple)):
        return "sequence"
    if isinstance(value, (int, float)):
        return "number"
    return "text"


@register.filter
def isodate(value: Any, fmt: str = "%d-%m-%Y") -> str:
    """Reformat an ISO date string, leaving anything unparseable alone.

    For a date that arrived as text — out of JSON config or an API — where
    Django's own date filter needs a date object.
    """
    if not value:
        return ""
    try:
        return datetime.datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime(fmt)
    except (TypeError, ValueError):
        return value


@register.filter
def to_json(value: Any) -> str:
    """A value as JSON, for a data attribute or an inline script tag.

    Escaped so the result cannot break out of the tag holding it: a string
    containing ``</script>`` would otherwise close it.
    """
    if value is None:
        return ""
    return json.dumps(value).translate(SCRIPT_ESCAPES)


@register.simple_tag
def icon(stored, size=18, css_class="pl-icon"):
    """Draw a stored icon name.

        {% icon page.menu_icon %}
        {% icon "plinta:chevron-down" size=14 %}

    Empty, unregistered or unknown draws nothing: an icon sits beside a label
    that already says what the thing is, so a gap beats a broken box.
    """
    from plinta.utils.icons import render

    return render(stored, size=size, css_class=css_class)

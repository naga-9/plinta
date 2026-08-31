"""Which icon a stored name draws.

A stored icon is `set:name` — `plinta:home`, `bi:house`, `fa:chart-line`.
**Write the prefix.** Everything plinta ships does, so a value says which set
it came from without the reader having to know what the default is, and it
matches `table_plinta` naming its implementation rather than assuming one.

An unprefixed value still resolves to core's set, and that is deliberate
rather than a second spelling to choose between: `menu_icon="home"` is what
somebody types, and drawing the icon beats drawing nothing while they work out
that a prefix was required. It is a forgiving read, not a supported style.

Core's set is registered through the same call a consumer uses. A private path
for the bundled one would make the door fiction, which is the argument that
put `table_plinta` through `register_component`.

    register_icon_set(
        "bi",
        render=lambda name: format_html('<i class="bi bi-{}"></i>', name),
    )

**A set that draws with a font is the consumer's to load.** Core requests
nothing at runtime — its own icons are inline SVG, so there is no stylesheet
to fetch, nothing to fail, and no flash before it arrives.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe

NAME = re.compile(r"[a-z][a-z0-9_]*")

#: The set an unprefixed name belongs to.
DEFAULT = "plinta"

#: Every icon core draws shares this. Held here rather than repeated 33 times.
WRAPPER = (
    '<svg class="{}" viewBox="0 0 24 24" width="{}" height="{}" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true" focusable="false">{}</svg>'
)


@dataclass(frozen=True)
class IconSet:
    """One way of drawing an icon."""

    name: str
    #: ``(name, size, css_class) -> markup``. Anything it returns is inserted
    #: unescaped, so it must build with `format_html`.
    render: Callable[..., SafeString]


class IconError(Exception):
    """A set was registered twice, or named unusably."""


_registry: dict[str, IconSet] = {}


def register_icon_set(name: str, *, render: Callable[..., SafeString]) -> IconSet:
    """Add a way of drawing icons.

    Raises:
        IconError: the name is taken, or is not lowercase ``[a-z][a-z0-9_]*``.
    """
    if not NAME.fullmatch(name):
        raise IconError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in _registry:
        raise IconError(f"{name!r} is already registered")
    _registry[name] = IconSet(name=name, render=render)
    return _registry[name]


def registered() -> list[str]:
    """Every set, by name."""
    return sorted(_registry)


def split(stored: str) -> tuple[str, str]:
    """``"bi:house"`` -> ``("bi", "house")``; ``"home"`` -> ``("plinta", "home")``."""
    stored = (stored or "").strip()
    if ":" in stored:
        prefix, _, name = stored.partition(":")
        return prefix.strip(), name.strip()
    return DEFAULT, stored


def render(stored: str, *, size: int = 18, css_class: str = "pl-icon") -> SafeString:
    """The markup for one stored icon name, or nothing.

    **Nothing** for an empty value, an unregistered set, or a name that set
    does not have. An icon is decoration beside a label that already says what
    the thing is, so a missing one should leave a gap rather than a broken
    box — the same degradation an unregistered component makes.
    """
    prefix, name = split(stored)
    if not name:
        return mark_safe("")
    icon_set = _registry.get(prefix)
    if icon_set is None:
        return mark_safe("")
    return icon_set.render(name, size=size, css_class=css_class)


def plinta_icon(name: str, *, size: int = 18, css_class: str = "pl-icon") -> SafeString:
    """Core's own: inline SVG, taking its colour from whatever it sits in."""
    from plinta.design.icons import ICONS

    inner = ICONS.get(name)
    if inner is None:
        return mark_safe("")
    # `inner` is our own path data, never a consumer's input. `name`, `size`
    # and `css_class` reach the attributes through format_html.
    return format_html(WRAPPER, css_class, size, size, mark_safe(inner))


def register_defaults() -> None:
    """Register core's set. Called from `AppConfig.ready()`."""
    if DEFAULT not in _registry:
        register_icon_set(DEFAULT, render=plinta_icon)

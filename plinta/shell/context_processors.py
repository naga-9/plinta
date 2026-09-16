"""The shell's own data, available to every template it renders."""
from __future__ import annotations

from typing import Any

from django.conf import settings


def branding(request) -> dict[str, Any]:
    """What the chrome calls this installation, and what colour it wears.

    `topbar_color` pins the topbar in light mode so staging does not look like
    production. It is unset by default, which is the only way to be sure a
    colour someone chose is the one they see.
    """
    return {
        "site_name": getattr(settings, "PLINTA_SITE_NAME", "plinta"),
        "topbar_color": getattr(settings, "TOPBAR_COLOR", ""),
    }


def menu(request) -> dict[str, Any]:
    """The sidebar: the pages this viewer may open, and the fixed links.

    Built per request rather than cached: it depends on the viewer's
    permissions, and a cache keyed by user is a cache invalidated by a grant.
    """
    from plinta.shell.menu import build
    from plinta.shell.topbar import visible_items

    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"menu": [], "topbar_items": []}
    return {
        "menu": build(user),
        "topbar_items": visible_items(user),
    }


def styles(request) -> dict:
    """The sheets and scripts every page loads, beyond core's own."""
    from plinta.utils.assets import scripts, stylesheets

    return {
        "plinta_stylesheets": stylesheets(),
        "plinta_scripts": scripts(),
    }

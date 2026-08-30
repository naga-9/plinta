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
    """The sidebar tree, filtered to what this viewer may open.

    Built per request rather than cached: it depends on the viewer's
    permissions, and a cache keyed by user is a cache invalidated by a grant.
    """
    from plinta.pages.menu import build

    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"menu_sections": []}
    return {"menu_sections": build(user)}

"""What must be true at boot for a form's stored layout to mean anything."""
from __future__ import annotations

from django.core.checks import Warning as CheckWarning, register


@register()
def check_form_layouts(app_configs=None, **kwargs) -> list[CheckWarning]:
    """Every registered layout names a template that can be loaded.

    A layout is named in a saved block and drawn on one screen, so a typo or a
    template that never shipped surfaces months later on the page that uses
    it. Rendering will not report it — a missing layout falls back to the
    stacked body so the page still draws — which is exactly why the check
    has to.

    Reads no rows, so it raises normally.
    """
    from django.template import TemplateDoesNotExist
    from django.template.loader import get_template

    from plinta.components.layouts import _registry

    problems = []
    for name, path in sorted(_registry.items()):
        try:
            get_template(path)
        except TemplateDoesNotExist:
            problems.append(
                CheckWarning(
                    f"form layout {name!r} draws with {path!r}, which no "
                    f"loader can find.",
                    hint="Ship the template with the app that registers the "
                    "layout, and check the path.",
                    id="plinta.components.W001",
                )
            )
    return problems

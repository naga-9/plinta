"""Drawing a state as a chip, in whatever colour the state declares.

The colour is a class name rather than a value, so core's token system draws
it and this app names no palette.
"""
from __future__ import annotations

from django.utils.html import format_html

from plinta.renderers.fields import register_field_renderer


def state_labels(model) -> dict[str, tuple[str, str]]:
    """`{code: (label, colour)}` for one model's active workflow."""
    from django.contrib.contenttypes.models import ContentType

    from plinta.contrib.workflow.models import Workflow

    workflow = Workflow.objects.filter(
        content_type=ContentType.objects.get_for_model(model), is_active=True
    ).first()
    if workflow is None:
        return {}
    return {s.code: (s.label, s.colour) for s in workflow.states.all()}


def register() -> None:
    """Register the renderer. Called from `AppConfig.ready()`."""

    @register_field_renderer("workflow_state")
    def workflow_state(value, *, obj=None, field=None, user=None, **kwargs):
        """A state code as its label, in a chip.

        Falls back to the raw code when nothing describes it — a state removed
        from a workflow leaves rows still holding its code, and showing the
        code is more useful than showing nothing.
        """
        code = value or ""
        if not code:
            return ""
        label, colour = state_labels(type(obj)).get(code, (code, ""))
        return format_html(
            '<span class="pl-chip {}">{}</span>', colour or "", label
        )

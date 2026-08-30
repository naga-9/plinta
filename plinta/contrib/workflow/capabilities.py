"""The status panel: where a row is, where it may go, and where it has been.

A capability rather than a component, because it is about **one record** and
hangs off a detail page. A component draws rows; this draws a row's state.
"""
from __future__ import annotations

from plinta.blocks.capabilities import register_capability


def governed_models() -> set[type]:
    """Every model an active workflow governs. Computed once.

    Read from the rows rather than from a registry in code: a workflow is
    data, so which models have one is a question for the database.
    """
    from django.db import DatabaseError

    from plinta.contrib.workflow.models import Workflow

    try:
        return {
            workflow.model
            for workflow in Workflow.objects.filter(is_active=True).select_related(
                "content_type"
            )
            if workflow.model is not None
        }
    except DatabaseError:
        # Asked before migrate, which is when a boot check runs.
        return set()


def register() -> None:
    """Register the capability. Called from `AppConfig.ready()`."""
    register_capability(
        "workflow",
        "Status",
        applies_to=lambda obj, user=None, **kw: getattr(obj, "pk", None) is not None,
        supports=lambda model, state=None, **kw: model in (state or set()),
        prepare=governed_models,
        template="plinta/workflow/section.html",
        order=50,
    )

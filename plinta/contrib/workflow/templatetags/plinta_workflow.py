"""What the status panel needs, in one call.

One tag rather than four, so the panel makes one pass over the workflow rather
than asking the database once per question.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django import template

from plinta.contrib.workflow import services

register = template.Library()


@dataclass(frozen=True)
class Panel:
    """Everything the section draws."""

    workflow: Any = None
    state: Any = None
    moves: list = None
    history: list = None


@register.simple_tag
def workflow_panel(record: Any, user: Any) -> Panel:
    """The row's workflow, where it is, where it may go, and where it has been.

    Returns an empty panel for a model no workflow governs, so the template
    draws nothing rather than guarding every line.
    """
    if record is None or getattr(record, "pk", None) is None:
        return Panel()
    workflow = services.workflow_for(record)
    if workflow is None:
        return Panel()

    code = services.state_of(record, workflow)
    state = next((s for s in workflow.states.all() if s.code == code), None)
    return Panel(
        workflow=workflow,
        state=state,
        moves=services.available(record, user),
        history=services.history(record),
    )

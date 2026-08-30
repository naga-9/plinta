"""Registering a model, asking what it may do, and doing it.

Three gates on every move, and all three must hold:

1. the **permission** minted for that transition — about the person
2. the **row policy**, through `can(user, "change", obj)` — about their reach
3. the **guard**, if the transition names one — about the row itself

Separate because they answer different questions. No grant can express "this
order has open lines", and no condition should decide who is allowed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.db import transaction

from plinta.contrib.workflow import guards, permissions
from plinta.events import signals

logger = logging.getLogger(__name__)


class TransitionDenied(Exception):
    """The move was refused, and by what."""

    def __init__(self, reason: str, *, gate: str = ""):
        self.gate = gate
        super().__init__(reason)


@dataclass(frozen=True)
class Move:
    """One transition offered on a row, and whether it may be taken."""

    transition: Any
    permitted: bool
    reason: str = ""

    @property
    def label(self) -> str:
        return str(self.transition)


def workflow_for(obj: Any):
    """The active workflow governing this row's model, or None.

    Bound by content type, so a consumer's model neither inherits from this
    app nor points at it.
    """
    from django.contrib.contenttypes.models import ContentType

    from plinta.contrib.workflow.models import Workflow

    return (
        Workflow.objects.filter(
            content_type=ContentType.objects.get_for_model(type(obj)), is_active=True
        )
        .prefetch_related("states")
        .first()
    )


def state_of(obj: Any, workflow=None) -> str:
    """The code this row is in, read from the model's own field."""
    workflow = workflow or workflow_for(obj)
    if workflow is None:
        return ""
    return getattr(obj, workflow.state_field, "") or ""


def set_initial(obj: Any, workflow=None) -> str:
    """Put a row in its starting state if it has none. Returns the state.

    Called rather than triggered, because a model this app does not own has no
    save this app may hook — which is the price of registration over
    inheritance, and the reason it is a one-line call in a consumer's create.
    """
    workflow = workflow or workflow_for(obj)
    if workflow is None or state_of(obj, workflow):
        return state_of(obj, workflow)
    initial = workflow.initial()
    if initial is None:
        return ""
    setattr(obj, workflow.state_field, initial.code)
    return initial.code


def available(obj: Any, user: Any) -> list[Move]:
    """Every transition out of this row's state, with why each is refused.

    Refused ones are returned rather than filtered out, so a screen can grey a
    button and say why instead of hiding it — a move that vanishes reads as a
    missing feature.
    """
    workflow = workflow_for(obj)
    if workflow is None:
        return []
    current = state_of(obj, workflow)
    moves = []
    for candidate in workflow.transitions.filter(
        from_state__code=current
    ).select_related("from_state", "to_state"):
        permitted, reason = check(obj, candidate, user, workflow=workflow)
        moves.append(Move(transition=candidate, permitted=permitted, reason=reason))
    return moves


def check(obj: Any, transition: Any, user: Any, workflow=None) -> tuple[bool, str]:
    """Whether this move may be made, and why not. Never raises."""
    from plinta.permissions import can

    workflow = workflow or transition.workflow
    model = workflow.model
    if model is None:
        return False, "the model this workflow governs is not installed"

    if state_of(obj, workflow) != transition.from_state.code:
        return False, "the row has moved on since this was offered"

    required = permissions.full_codename(
        model, transition.from_state.code, transition.to_state.code
    )
    if not user_has(user, required):
        return False, "you do not have permission to make this move"

    if not can(user, "change", obj):
        return False, "you may not change this record"

    if transition.guard:
        return guards.evaluate(transition.guard, obj, user, transition)
    return True, ""


def user_has(user: Any, codename: str) -> bool:
    return bool(user is not None and user.has_perm(codename))


@transaction.atomic
def execute(obj: Any, transition: Any, user: Any, *, source: str = "") -> Any:
    """Make the move, or refuse it.

    Atomic: the state change and its event either both happen or neither does.
    The event fires **after** the row is saved, so a listener that reads the
    object sees where it now is rather than where it was.

    Raises:
        TransitionDenied: any of the three gates refused.
    """
    workflow = transition.workflow
    permitted, reason = check(obj, transition, user, workflow=workflow)
    if not permitted:
        raise TransitionDenied(reason)

    from_code = transition.from_state.code
    to_code = transition.to_state.code

    setattr(obj, workflow.state_field, to_code)
    obj.save(update_fields=[workflow.state_field])

    signals.emit_state_changed(
        obj,
        from_state=from_code,
        to_state=to_code,
        actor=user,
        source=source,
        metadata={
            "workflow": workflow.code,
            "transition": transition.pk,
            "label": str(transition),
        },
    )
    return obj


def history(obj: Any) -> list:
    """Where this row has been, newest first.

    Read from the audit trail, which records `state_changed` like any other
    write. With that app absent this returns nothing and a panel says so — the
    state machine is unaffected, and only the record of where a row has been
    is missing, which is exactly what an audit trail is.
    """
    from django.apps import apps

    if not apps.is_installed("plinta.contrib.audit"):
        return []

    from django.contrib.contenttypes.models import ContentType

    from plinta.contrib.audit.models import AuditEntry

    return list(
        AuditEntry.objects.filter(
            action="state_changed",
            content_type=ContentType.objects.get_for_model(type(obj)),
            object_id=obj.pk,
        )
    )

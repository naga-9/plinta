"""Permissions follow the transitions, exactly as they follow the columns.

Saving a transition mints its permission; renaming a state renames it in
place; deleting one removes it. The `pre_save` exists for the same reason a
column's does — `post_save` sees only the new value, so without it a rename is
indistinguishable from a new transition and every grant on it is dropped.
"""
from __future__ import annotations

import logging

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from plinta.contrib.workflow import permissions
from plinta.contrib.workflow.models import WorkflowState, WorkflowTransition

logger = logging.getLogger(__name__)

#: Where `pre_save` leaves the stored codes for `post_save` to compare.
OLD_CODES = "_plinta_old_transition_codes"
OLD_STATE_CODE = "_plinta_old_state_code"


def stored_codes(transition: WorkflowTransition) -> tuple[str, str] | None:
    """The state codes this transition had in the database, or None if new."""
    row = (
        WorkflowTransition.objects.filter(pk=transition.pk)
        .select_related("from_state", "to_state")
        .first()
    )
    return (row.from_state.code, row.to_state.code) if row else None


@receiver(pre_save, sender=WorkflowTransition)
def remember_transition_codes(sender, instance, **kwargs):
    setattr(instance, OLD_CODES, stored_codes(instance) if instance.pk else None)


@receiver(post_save, sender=WorkflowTransition)
def sync_transition_permission(sender, instance, created, **kwargs):
    model = instance.workflow.model
    if model is None:
        return
    old = getattr(instance, OLD_CODES, None)
    new = (instance.from_state.code, instance.to_state.code)
    if old and old != new:
        permissions.rename(model, old, new)
    permissions.mint(instance)
    setattr(instance, OLD_CODES, new)


@receiver(post_delete, sender=WorkflowTransition)
def remove_transition_permission(sender, instance, **kwargs):
    model = instance.workflow.model
    if model is not None:
        permissions.remove(
            model, instance.from_state.code, instance.to_state.code
        )


@receiver(pre_save, sender=WorkflowState)
def remember_state_code(sender, instance, **kwargs):
    stored = (
        WorkflowState.objects.filter(pk=instance.pk)
        .values_list("code", flat=True)
        .first()
        if instance.pk
        else None
    )
    setattr(instance, OLD_STATE_CODE, stored)


@receiver(post_save, sender=WorkflowState)
def rename_permissions_of_a_renamed_state(sender, instance, created, **kwargs):
    """A state's code is half of every codename that mentions it.

    Renaming one therefore renames a permission per transition touching it —
    each in place, so a grant survives. Missing this is how somebody renames a
    state and quietly revokes everybody.
    """
    old = getattr(instance, OLD_STATE_CODE, None)
    if not old or old == instance.code:
        return
    model = instance.workflow.model
    if model is None:
        return
    for transition in instance.transitions_out.select_related("to_state"):
        permissions.rename(
            model, (old, transition.to_state.code), (instance.code, transition.to_state.code)
        )
    for transition in instance.transitions_in.select_related("from_state"):
        permissions.rename(
            model, (transition.from_state.code, old), (transition.from_state.code, instance.code)
        )
    setattr(instance, OLD_STATE_CODE, instance.code)


def connect() -> None:
    """The receivers are registered by decorator; `ready()` imports the module.

    Kept as a function so the app config reads the same as the others, and so
    there is one place to look for what this app subscribes to.
    """

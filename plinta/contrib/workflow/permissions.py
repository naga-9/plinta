"""One permission per transition, minted from the row that describes it.

`transition_order_open_to_closed` is grantable on its own, so "may move an
order to closed" is separable from "may edit an order" — which is the whole
reason a transition carries a permission rather than reusing `change_*`.

Renaming a state renames the permission **in place**. A grant points at a
permission's primary key, so deleting and recreating one drops every grant on
it silently, which is the failure this exists to prevent.
"""
from __future__ import annotations

from typing import Any


def codename(model, from_code: str, to_code: str) -> str:
    """The codename for one transition, without its app label.

    Built from the state **codes**, which are identifiers rather than labels —
    so renaming what a state is called on screen changes nothing here.
    """
    return f"transition_{model._meta.model_name}_{from_code}_to_{to_code}"


def label_for(model, from_code: str, to_code: str) -> str:
    return f"Can move {model._meta.verbose_name} from {from_code} to {to_code}"


def mint(transition: Any) -> bool:
    """Ensure this transition's permission exists. Returns whether it was new."""
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    model = transition.workflow.model
    if model is None:
        return False
    name = codename(model, transition.from_state.code, transition.to_state.code)
    _, created = Permission.objects.get_or_create(
        content_type=ContentType.objects.get_for_model(model),
        codename=name,
        defaults={
            "name": label_for(
                model, transition.from_state.code, transition.to_state.code
            )
        },
    )
    return created


def rename(model, old: tuple[str, str], new: tuple[str, str]) -> int:
    """Move a transition's permission to new state codes, keeping its grants.

    Returns how many were renamed — zero when nothing had been minted yet,
    which is not an error.
    """
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    if old == new:
        return 0
    content_type = ContentType.objects.get_for_model(model)
    return Permission.objects.filter(
        content_type=content_type, codename=codename(model, *old)
    ).update(
        codename=codename(model, *new), name=label_for(model, *new)
    )


def remove(model, from_code: str, to_code: str) -> int:
    """Delete a transition's permission. Returns how many were removed."""
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    deleted, _ = Permission.objects.filter(
        content_type=ContentType.objects.get_for_model(model),
        codename=codename(model, from_code, to_code),
    ).delete()
    return deleted


def full_codename(model, from_code: str, to_code: str) -> str:
    """``app_label.codename``, as `has_perm` wants it."""
    return f"{model._meta.app_label}.{codename(model, from_code, to_code)}"


def rebuild(workflow: Any) -> list[str]:
    """Mint every transition's permission for one workflow.

    The idempotent backstop for anything that drifts — a bulk import that used
    `bulk_create`, which fires no `post_save` at all.
    """
    return [
        codename(
            workflow.model, t.from_state.code, t.to_state.code
        )
        for t in workflow.transitions.select_related("from_state", "to_state")
        if mint(t)
    ]

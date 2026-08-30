"""Granting and revoking, with the one rule that stops self-promotion.

**A non-superuser may only grant permissions they themselves hold.** Without
it, anyone who can administer permissions can grant themselves anything, and
the console's own access check becomes the only thing standing between a user
and every permission in the system.

Revoking is unrestricted: removing access is not escalation.

This module enforces escalation only. Whether someone may administer
permissions at all is an ordinary `can(user, "change", Permission)` question,
asked by whatever exposes the screen.
"""
from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction


class PermissionEscalation(Exception):
    """A granter tried to hand out a permission they do not hold."""

    def __init__(self, codenames: list[str]):
        self.codenames = sorted(codenames)
        super().__init__(
            "cannot grant permissions the granter does not hold: "
            + ", ".join(self.codenames)
        )


def _is_superuser(user) -> bool:
    return bool(getattr(user, "is_superuser", False))


def _codename(permission) -> str:
    return f"{permission.content_type.app_label}.{permission.codename}"


def can_grant(granter, permission) -> bool:
    """Whether ``granter`` may hand out this permission.

    A superuser may grant anything. Anyone else may grant only what they hold,
    directly or through a group — Django's own ``has_perm`` answers both.
    """
    if _is_superuser(granter):
        return True
    return granter.has_perm(_codename(permission))


def grantable(granter, permissions: Iterable) -> list:
    """The subset of ``permissions`` that ``granter`` may hand out.

    For a console that should offer only what the user can actually give,
    rather than offering everything and refusing on save.
    """
    return [p for p in permissions if can_grant(granter, p)]


def _target_relation(target):
    """A user's or a group's permission set."""
    relation = getattr(target, "user_permissions", None) or getattr(target, "permissions", None)
    if relation is None:
        raise TypeError(f"{target!r} has neither user_permissions nor permissions")
    return relation


def grant(granter, target, permissions: Iterable) -> list:
    """Grant every permission in ``permissions`` to ``target``.

    All or nothing: if the granter may not hand out one of them, nothing is
    applied. A partial grant would leave the caller unable to tell what
    happened, and re-running it would compound the difference.

    Returns the permissions actually added — one the target already held is
    not an error and is not counted.

    Raises:
        PermissionEscalation: the granter does not hold one of them.
    """
    permissions = list(permissions)
    refused = [_codename(p) for p in permissions if not can_grant(granter, p)]
    if refused:
        raise PermissionEscalation(refused)

    relation = _target_relation(target)
    held = set(relation.values_list("pk", flat=True))
    added = [p for p in permissions if p.pk not in held]
    if added:
        with transaction.atomic():
            relation.add(*added)
    return added


def revoke(granter, target, permissions: Iterable) -> list:
    """Remove every permission in ``permissions`` from ``target``.

    Unrestricted by design: taking access away cannot escalate anyone. The
    ``granter`` is taken so the call site reads symmetrically with ``grant``
    and so an audit listener sees who did it.

    Returns the permissions actually removed.
    """
    permissions = list(permissions)
    relation = _target_relation(target)
    held = set(relation.values_list("pk", flat=True))
    removed = [p for p in permissions if p.pk in held]
    if removed:
        with transaction.atomic():
            relation.remove(*removed)
    return removed


def can_add_to_group(granter, group) -> bool:
    """Whether ``granter`` may put someone in ``group``.

    Bounded by the permissions the group carries, not by its name: adding a
    user to a group grants them everything in it, so the granter must hold all
    of it. A group called "Read only" that carries `delete_book` is exactly the
    case a name-based rule would miss.
    """
    if _is_superuser(granter):
        return True
    return all(can_grant(granter, p) for p in group.permissions.select_related("content_type"))


def add_to_group(granter, user, group) -> bool:
    """Put ``user`` in ``group``. Returns whether it changed anything.

    Raises:
        PermissionEscalation: the group carries permissions the granter lacks.
    """
    if not can_add_to_group(granter, group):
        refused = [
            _codename(p)
            for p in group.permissions.select_related("content_type")
            if not can_grant(granter, p)
        ]
        raise PermissionEscalation(refused)

    if user.groups.filter(pk=group.pk).exists():
        return False
    user.groups.add(group)
    return True


def remove_from_group(granter, user, group) -> bool:
    """Take ``user`` out of ``group``. Unrestricted, as revoking is."""
    if not user.groups.filter(pk=group.pk).exists():
        return False
    user.groups.remove(group)
    return True

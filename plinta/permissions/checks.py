"""What must be true at boot for a permission decision to mean anything.

A policy that names a permission nobody minted refuses every row and says
nothing about why, so it is reported here rather than discovered in production.

Only what this layer can see. Checks needing a DataSource belong to the layer
that has one.
"""
from __future__ import annotations

from django.core.checks import Error, register

from plinta.permissions.policies import registered
from plinta.permissions.rules import HasPerm, walk


def declared_codenames() -> set[tuple[type, str, str]]:
    """Every ``HasPerm`` codename a registered policy composes.

    Returns ``(model, action, codename)`` so a report can say where it came from.
    """
    found = set()
    for model, policy in registered().items():
        for action in policy.actions():
            rule = policy.rule_for(action)
            if rule is None:
                continue
            for node in walk(rule):
                if isinstance(node, HasPerm):
                    found.add((model, action, node.codename))
    return found


@register()
def check_haspermissions_exist(app_configs=None, **kwargs) -> list[Error]:
    """Every ``HasPerm`` in a policy names a permission that exists.

    A missing one is not a silent no-op: the rule denies, so the policy refuses
    rows it was written to admit.
    """
    from django.contrib.auth.models import Permission
    from django.db import DatabaseError

    declared = declared_codenames()
    if not declared:
        return []

    try:
        existing = {
            f"{app_label}.{codename}"
            for app_label, codename in Permission.objects.values_list(
                "content_type__app_label", "codename"
            )
        }
    except DatabaseError:
        # Checks run before migrate on a fresh database. Nothing to validate
        # against yet, and failing here would block the migration that fixes it.
        return []

    return [
        Error(
            f"{model.__name__} policy: {action} names {codename!r}, which no "
            f"permission matches — the rule will deny every row.",
            hint="Mint the permission, or correct the codename in the policy.",
            id="plinta.permissions.E001",
            obj=model,
        )
        for model, action, codename in sorted(declared, key=lambda d: (d[0].__name__, d[1]))
        if codename not in existing
    ]

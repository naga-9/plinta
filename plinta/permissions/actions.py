"""The actions a model can carry, beyond Django's four.

Django mints ``add`` / ``change`` / ``delete`` / ``view`` for every model. An
action beyond those — ``export``, ``import``, ``publish``, ``share`` — is
registered here and minted per model, because plinta cannot add ``Meta.permissions``
to a consumer's model.

Two kinds, and classifying a new one correctly is the whole difficulty:

**Row actions** filter rows. ``view``, ``change`` and ``delete`` are these, and
a policy narrows them.

**Capabilities** are a model-level yes or no. ``export`` is one: there is no set
of exportable rows distinct from viewable ones, so it composes with the row
filter for ``view`` rather than carrying a filter of its own.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Model

#: What Django mints itself. Registering one of these is a mistake, not a no-op.
DJANGO_ACTIONS = frozenset({"add", "change", "delete", "view"})


@dataclass(frozen=True)
class Action:
    """A registered action, and what it does to rows."""

    name: str
    label: str
    #: True when the action filters rows, False when it is a model-level
    #: capability that composes with another action's filter.
    filters_rows: bool = False


class ActionError(Exception):
    """An action was registered twice, under an unusable name, or shadows Django's."""


_registry: dict[str, Action] = {}


def register_action(name: str, label: str = "", *, filters_rows: bool = False) -> Action:
    """Register an action so it can be minted, granted and checked.

    Args:
        name: lowercase ``[a-z][a-z0-9_]*``; the codename becomes
            ``{action}_{model}``.
        label: what a permission console shows. Defaults to the name.
        filters_rows: whether a policy may narrow which rows it applies to.
            Leave False for a capability like ``export``, which composes with
            the row filter for ``view`` instead of carrying its own.

    Raises:
        ActionError: the name is taken, unusable, or one Django already mints.
    """
    import re

    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ActionError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in DJANGO_ACTIONS:
        raise ActionError(f"{name!r} is minted by Django; registering it would shadow it")
    if name in _registry:
        raise ActionError(f"{name!r} is already registered")
    _registry[name] = Action(name=name, label=label or name, filters_rows=filters_rows)
    return _registry[name]


def registered() -> dict[str, Action]:
    """Every registered action, by name."""
    return dict(_registry)


def mint_action(model: type[Model], action: str) -> bool:
    """Create ``{action}_{model}`` for this model. Returns whether it was new.

    Called per registered DataSource by the layer that has one — this module
    knows a model and an action, never which models are registered.

    Raises:
        ActionError: the action is not registered. Minting an unregistered one
            would put a permission in the console that nothing ever checks.
    """
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    if action not in _registry:
        raise ActionError(f"{action!r} is not registered; call register_action first")

    _, created = Permission.objects.get_or_create(
        content_type=ContentType.objects.get_for_model(model),
        codename=f"{action}_{model._meta.model_name}",
        defaults={"name": f"Can {_registry[action].label} {model._meta.verbose_name}"},
    )
    return created


def mint_for(model: type[Model]) -> list[str]:
    """Mint every registered action for one model. Returns the ones created."""
    return [a for a in sorted(_registry) if mint_action(model, a)]

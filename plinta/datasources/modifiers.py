"""Named callables that narrow a queryset.

Registered by name, never resolved from a dotted path in configuration, so a
stored value cannot name arbitrary importable code. A block stores the name; the
registry resolves it.
"""
from __future__ import annotations

import re
from collections.abc import Callable

from django.db.models import QuerySet

Modifier = Callable[..., QuerySet]

_registry: dict[str, Modifier] = {}


class ModifierError(Exception):
    """A modifier was registered twice, named unusably, or asked for by a name
    nothing registered."""


def register_queryset_modifier(name: str, fn: Modifier | None = None):
    """Register a modifier, as a call or a decorator.

    The function takes ``(queryset, user, **kwargs)`` and returns a queryset. It
    **may narrow and must not widen** — every caller above this layer assumes
    what it receives is already permission-filtered, and a modifier that adds
    rows would defeat that silently.

    Raises:
        ModifierError: the name is taken, or is not lowercase
            ``[a-z][a-z0-9_]*``.
    """
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ModifierError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in _registry:
        raise ModifierError(f"{name!r} is already registered")

    def _register(func: Modifier) -> Modifier:
        _registry[name] = func
        return func

    return _register if fn is None else _register(fn)


def registered() -> dict[str, Modifier]:
    """Every registered modifier, by name."""
    return dict(_registry)


def get_modifier(name: str) -> Modifier:
    """The modifier registered under ``name``.

    Raises:
        ModifierError: nothing is registered under that name. Configuration
            naming a modifier that does not exist fails here rather than
            rendering every row it was meant to hide.
    """
    try:
        return _registry[name]
    except KeyError:
        known = ", ".join(sorted(_registry)) or "none"
        raise ModifierError(f"no queryset modifier named {name!r} (registered: {known})") from None


def apply_modifier(name: str, queryset: QuerySet, user, **kwargs) -> QuerySet:
    """Run a registered modifier over ``queryset``."""
    return get_modifier(name)(queryset, user=user, **kwargs)

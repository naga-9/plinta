"""Which component a block's ``component_type`` names.

`find` returns None for a type nothing registered, which is how a block renders
an **empty slot** — a normal state, not an error. A page must not break because
a component was removed, exactly as it does not break when a viewer lacks
permission on a placed block.

`get` raises, for a caller that already knows the type is installed.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plinta.components.base import Component

NAME = re.compile(r"[a-z][a-z0-9_]*")


class ComponentError(Exception):
    """A component was registered twice, named unusably, or asked for by a name
    nothing registered."""


_registry: dict[str, Component] = {}


def register_component(name: str, *, label: str = ""):
    """Register a component under a registry key, as a decorator on the class.

        @register_component("heatmap", label="Heat map")
        class HeatmapComponent(Component):
            config_schema = HeatmapConfig

    Called from the owning app's ``AppConfig.ready()``. The class is
    instantiated once here, since a component holds no per-call state.

    Raises:
        ComponentError: the name is taken, or is not lowercase
            ``[a-z][a-z0-9_]*``.
    """
    if not NAME.fullmatch(name):
        raise ComponentError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in _registry:
        raise ComponentError(f"{name!r} is already registered")

    def _register(cls):
        component = cls()
        if label:
            component.label = label
        _registry[name] = component
        return cls

    return _register


def registered() -> dict[str, Component]:
    """Every registered component, by registry key. The picker's contents."""
    return dict(_registry)


def is_registered(name: str) -> bool:
    """Whether this component type is installed."""
    return name in _registry


def find(name: str) -> Component | None:
    """The component named ``name``, or None if nothing registered it.

    None is the empty-slot path: a block referencing a component whose package
    was removed degrades rather than raising.
    """
    return _registry.get(name)


def get(name: str) -> Component:
    """The component named ``name``.

    Raises:
        ComponentError: nothing is registered under it.
    """
    try:
        return _registry[name]
    except KeyError:
        known = ", ".join(sorted(_registry)) or "none"
        raise ComponentError(f"no component named {name!r} (registered: {known})") from None

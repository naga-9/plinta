"""Capabilities: what an app contributes to an edit form, and to the matrix.

A capability lives here because it contributes to an **edit form**, which is a
block concern. Core registers none of them and knows none of them by name: an
app registers its own, and core renders whatever the registry holds.

Two probes, two questions, deliberately different:

``applies_to(obj)``   does this apply to *this row*?      — the edit form
``supports(model)``   does this model support it at all?  — the matrix

The matrix asks once per model and the form once per row, which is why the
matrix probe may take a ``state`` prepared once for every model rather than
issuing a query each.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

NAME = re.compile(r"[a-z][a-z0-9_]*")


@dataclass(frozen=True)
class Capability:
    """One app's contribution, both aspects registered together."""

    name: str
    label: str
    #: Does this apply to this row? None means it always does.
    applies_to: Callable[..., bool] | None = None
    #: Does this model support it at all? None means every model does.
    supports: Callable[..., bool] | None = None
    #: Computed once for every model, so ``supports`` stays a lookup rather
    #: than a query per model.
    prepare: Callable[[], Any] | None = None
    #: Where the edit form draws it.
    template: str = ""
    order: int = field(default=100)


class CapabilityError(Exception):
    """A capability was registered twice, or under an unusable name."""


_registry: dict[str, Capability] = {}


def register_capability(
    name: str,
    label: str = "",
    *,
    applies_to: Callable[..., bool] | None = None,
    supports: Callable[..., bool] | None = None,
    prepare: Callable[[], Any] | None = None,
    template: str = "",
    order: int = 100,
) -> Capability:
    """Register one capability, both aspects at once.

        register_capability(
            "comments",
            "Comments",
            applies_to=lambda obj, **kw: obj.pk is not None,
            supports=lambda model, state=None, **kw: model in state,
            prepare=commented_models,
            template="comments/section.html",
        )

    Called from the owning app's ``AppConfig.ready()``. Registering an app's
    capability from anywhere else is core knowing contrib by name.

    Raises:
        CapabilityError: the name is taken, or is not lowercase
            ``[a-z][a-z0-9_]*``.
    """
    if not NAME.fullmatch(name):
        raise CapabilityError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in _registry:
        raise CapabilityError(f"{name!r} is already registered")
    capability = Capability(
        name=name,
        label=label or name.replace("_", " ").title(),
        applies_to=applies_to,
        supports=supports,
        prepare=prepare,
        template=template,
        order=order,
    )
    _registry[name] = capability
    return capability


def registered() -> list[Capability]:
    """Every registered capability, in display order."""
    return sorted(_registry.values(), key=lambda c: (c.order, c.name))


def for_object(obj, user=None) -> list[Capability]:
    """The capabilities that apply to one row, in display order.

    What an edit form draws beside the fields.
    """
    return [
        c
        for c in registered()
        if c.applies_to is None or c.applies_to(obj=obj, user=user)
    ]


def matrix(models: list[type]) -> dict[type, list[Capability]]:
    """Which capabilities each model supports.

    ``prepare`` runs once per capability, not once per model, so a probe
    answering "is this model commentable" is a set lookup rather than a query.
    """
    prepared = {c.name: c.prepare() if c.prepare else None for c in registered()}
    return {
        model: [
            c
            for c in registered()
            if c.supports is None or c.supports(model=model, state=prepared[c.name])
        ]
        for model in models
    }

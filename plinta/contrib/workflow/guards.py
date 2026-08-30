"""Conditions a transition must satisfy beyond a permission.

"May close an order" is a permission. "This order has no open lines" is a
guard: it is about the row rather than the person, so no grant can express it
and no policy should — a policy narrows what a user may reach, and a guard
answers whether a move makes sense at all.

Registered by name, never resolved from a stored dotted path, so a transition
row cannot name arbitrary importable code.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

NAME = re.compile(r"[a-z][a-z0-9_]*")


@dataclass(frozen=True)
class Guard:
    """One registered condition."""

    name: str
    #: ``(obj, user, transition) -> bool | str``. A string is the reason it
    #: refused, shown to whoever tried.
    check: Callable[..., Any]
    label: str = ""


class GuardError(Exception):
    """A guard was registered twice, named unusably, or asked for by a name
    nothing registered."""


_registry: dict[str, Guard] = {}


def register_guard(name: str, label: str = "", *, check: Callable[..., Any]) -> Guard:
    """Add a condition a transition may name.

        register_guard(
            "no_open_lines",
            check=lambda obj, **kw: not obj.lines.filter(open=True).exists()
                                    or "This order still has open lines.",
        )

    Return `True` to permit, `False` to refuse, or a **string** to refuse with
    a reason — which is what a screen shows instead of a button that silently
    does nothing.

    Raises:
        GuardError: the name is taken, or is not lowercase
            ``[a-z][a-z0-9_]*``.
    """
    if not NAME.fullmatch(name):
        raise GuardError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in _registry:
        raise GuardError(f"{name!r} is already registered")
    guard = Guard(name=name, check=check, label=label or name.replace("_", " "))
    _registry[name] = guard
    return guard


def registered() -> dict[str, Guard]:
    """Every guard, by name. What a transition may choose from."""
    return dict(_registry)


def get(name: str) -> Guard:
    """The guard registered under ``name``.

    Raises:
        GuardError: nothing is registered under it. A transition naming a
            guard that does not exist must not simply proceed — the condition
            was written down because somebody meant it to hold.
    """
    try:
        return _registry[name]
    except KeyError:
        known = ", ".join(sorted(_registry)) or "none"
        raise GuardError(f"no guard named {name!r} (registered: {known})") from None


def evaluate(name: str, obj: Any, user: Any, transition: Any) -> tuple[bool, str]:
    """Run a guard. Returns ``(permitted, reason)``.

    A guard that raises **refuses**, and says so. Permitting on error would
    let a broken condition wave through the transition it was written to stop.
    """
    guard = get(name)
    try:
        result = guard.check(obj=obj, user=user, transition=transition)
    except Exception as exc:  # noqa: BLE001 - a consumer's callable is not ours
        logger.exception("guard %r failed", name)
        return False, f"{guard.label} could not be checked: {exc}"
    if result is True:
        return True, ""
    if result is False or result is None:
        return False, f"{guard.label} was not satisfied"
    return False, str(result)

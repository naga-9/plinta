"""Registry for magic tokens inside filter-style values.

``{"date": "__CURRENT_QUARTER__"}`` resolves to a value at query time. A token
supplies a value only — never a field path and never an operator — so it cannot
widen a filter into fields its author never named.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

#: ``__NAME__``, uppercase; the registry is keyed by the lowercase name.
#:
#: Anchored with ``\A`` and ``\Z`` rather than ``^`` and ``$``, so the token is
#: the whole value under any match method: ``$`` also matches before a trailing
#: newline, and an unanchored pattern would find a token inside ``owner__ME__x``.
TOKEN = re.compile(r"\A__([A-Z][A-Z0-9_]*)__\Z")

_registry: dict[str, Callable[["Context"], Any]] = {}


@dataclass(frozen=True)
class Context:
    """What a resolver may depend on. A token is evaluated per request."""

    user: Any = None
    #: The row a detail page is about, when there is one. `utils` never
    #: learns what a Page is — it holds a value that a resolver may read.
    record: Any = None


class PlaceholderError(Exception):
    """A token was registered twice, or under an unusable name."""


def register_placeholder(name: str, fn: Callable[[Context], Any] | None = None):
    """Register a resolver, as a call or a decorator.

    Raises:
        PlaceholderError: the name is already taken, or is not lowercase
            ``[a-z][a-z0-9_]*``.
    """
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise PlaceholderError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in _registry:
        raise PlaceholderError(f"{name!r} is already registered")

    def _register(func):
        _registry[name] = func
        return func

    return _register if fn is None else _register(fn)


def registered() -> frozenset[str]:
    """Every registered token name."""
    return frozenset(_registry)


def resolve(value: Any, ctx: Context) -> Any:
    """Resolve one value if it is a token, otherwise return it unchanged.

    An unregistered token is returned as written. Blanking it would silently
    widen the filter that contains it.
    """
    if not isinstance(value, str):
        return value
    match = TOKEN.fullmatch(value)
    if match is None:
        return value
    fn = _registry.get(match.group(1).lower())
    return value if fn is None else fn(ctx)


def resolve_values(values: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Resolve every token in a filter-style dict, including inside lists."""
    out: dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, list):
            out[key] = [resolve(item, ctx) for item in value]
        else:
            out[key] = resolve(value, ctx)
    return out


def unresolved(values: dict[str, Any]) -> frozenset[str]:
    """Token names in ``values`` that nothing has registered."""
    found = set()
    for value in values.values():
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, str) and (m := TOKEN.fullmatch(item)):
                name = m.group(1).lower()
                if name not in _registry:
                    found.add(name)
    return frozenset(found)

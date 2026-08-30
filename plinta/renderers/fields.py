"""Field renderers: how one value is drawn, and what that costs in joins.

A column names a renderer; the renderer returns markup and declares the
relations it reads. The declaration is what lets `datasources` join for a
relation no column mentions (§6.5), which it cannot otherwise see.

Renderers here produce **HTML**. A spreadsheet or an email formats the value
with `format_value` instead, since a chip is markup and a cell is not.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from plinta.datasources.models import DataSourceField

NAME = re.compile(r"[a-z][a-z0-9_]*")


@dataclass(frozen=True)
class FieldRenderer:
    """A registered way of drawing one value."""

    name: str
    render: Callable[..., str]
    #: Relations the renderer reads that no column path names.
    select_related: tuple[str, ...] = ()
    prefetch_related: tuple[str, ...] = ()


class FieldRendererError(Exception):
    """A renderer was registered twice, named unusably, or asked for by a name
    nothing registered."""


_registry: dict[str, FieldRenderer] = {}


def register_field_renderer(
    name: str,
    *,
    select_related: Iterable[str] = (),
    prefetch_related: Iterable[str] = (),
):
    """Register a field renderer, as a decorator.

        @register_field_renderer("label_chips", prefetch_related=["labels"])
        def label_chips(value, *, obj, field, user):
            return format_html_join(" ", "<span>{}</span>", ((l,) for l in value))

    The function is called with keywords, so it may accept only what it uses.

    Declaring the relations it reads is the point of registering rather than
    duck-typing: derivation sees the column paths, and a renderer reaching
    ``obj.labels`` from a column called ``title`` is invisible to it.

    Raises:
        FieldRendererError: the name is taken, or is not lowercase
            ``[a-z][a-z0-9_]*``.
    """
    if not NAME.fullmatch(name):
        raise FieldRendererError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in _registry:
        raise FieldRendererError(f"{name!r} is already registered")

    def _register(fn: Callable[..., str]) -> Callable[..., str]:
        _registry[name] = FieldRenderer(
            name=name,
            render=fn,
            select_related=tuple(select_related),
            prefetch_related=tuple(prefetch_related),
        )
        return fn

    return _register


def registered() -> dict[str, FieldRenderer]:
    """Every registered field renderer, by name."""
    return dict(_registry)


def is_field_renderer(name: str) -> bool:
    """Whether anything is registered under this name."""
    return name in _registry


def get_field_renderer(name: str) -> FieldRenderer:
    """The renderer registered under ``name``.

    Raises:
        FieldRendererError: nothing is registered under it.
    """
    try:
        return _registry[name]
    except KeyError:
        known = ", ".join(sorted(_registry)) or "none"
        raise FieldRendererError(
            f"no field renderer named {name!r} (registered: {known})"
        ) from None


def joins_for(fields: Iterable[DataSourceField]) -> tuple[set[str], set[str]]:
    """The ``select_related`` and ``prefetch_related`` these columns' renderers need.

    Fed to ``prefetch.apply`` as ``extra_select`` and ``extra_prefetch``. A
    column naming an unregistered renderer contributes nothing here; the boot
    check reports it (§7.8).
    """
    select: set[str] = set()
    prefetch: set[str] = set()
    for field in fields:
        renderer = _registry.get(getattr(field, "renderer", "") or "")
        if renderer is not None:
            select |= set(renderer.select_related)
            prefetch |= set(renderer.prefetch_related)
    return select, prefetch


def render_field(
    value: Any, field: DataSourceField | None = None, *, obj: Any = None, user=None
) -> str:
    """Draw ``value`` for HTML, through the column's renderer if it names one.

    Falls back to ``format_value``, so a caller never asks whether a column has
    a renderer. Output is markup and is trusted: registering a renderer is the
    same trust as writing a template.
    """
    from plinta.renderers.format import format_value

    name = (getattr(field, "renderer", "") or "") if field is not None else ""
    if not name:
        return format_value(value, field)
    return get_field_renderer(name).render(value=value, obj=obj, field=field, user=user)

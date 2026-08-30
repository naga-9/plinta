"""Which renderer draws a format, and what stands in when none does.

`get` substitutes HTML for a format nothing registered, so a caller never asks
whether `contrib.export` is installed — a report defined against `xlsx` runs
without it and renders to screen (§2.5).

`require` does not substitute. A format a client asked for over HTTP and which
is not installed is a 404: substitution is for internal callers, not for
content negotiation.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plinta.renderers.base import Renderer

#: The format every other one falls back to.
HTML = "html"

NAME = re.compile(r"[a-z][a-z0-9_]*")


class RendererError(Exception):
    """A renderer was registered twice, named unusably, or required by a name
    nothing registered."""


_registry: dict[str, Renderer] = {}


def register_renderer(name: str):
    """Register the renderer for one format, as a decorator on the class.

        @register_renderer("csv")
        class CsvRenderer(Renderer):
            def render(self, rows, fields, config, user): ...

    Called from the owning app's ``AppConfig.ready()``. The class is
    instantiated once here, since a renderer holds no per-call state.

    Raises:
        RendererError: the name is taken, or is not lowercase
            ``[a-z][a-z0-9_]*``.
    """
    if not NAME.fullmatch(name):
        raise RendererError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in _registry:
        raise RendererError(f"{name!r} is already registered")

    def _register(cls):
        _registry[name] = cls()
        return cls

    return _register


def registered() -> dict[str, Renderer]:
    """Every registered renderer, by format."""
    return dict(_registry)


def is_registered(name: str) -> bool:
    """Whether this format has a renderer of its own."""
    return name in _registry


def get(name: str) -> Renderer:
    """The renderer for ``name``, or the HTML one when nothing registered it.

    So a block defined against a format its installation does not have still
    renders, to screen. A caller wanting the difference to matter uses
    ``require``.

    Raises:
        RendererError: ``name`` is unregistered and so is HTML, which means no
            renderer is installed at all.
    """
    renderer = _registry.get(name) or _registry.get(HTML)
    if renderer is None:
        raise RendererError(f"no renderer for {name!r}, and none for {HTML!r} either")
    return renderer


def require(name: str) -> Renderer:
    """The renderer for ``name``, or an error.

    For a format a client asked for by name: answering an `xlsx` request with
    an HTML page is worse than refusing it.

    Raises:
        RendererError: nothing is registered under ``name``.
    """
    try:
        return _registry[name]
    except KeyError:
        known = ", ".join(sorted(_registry)) or "none"
        raise RendererError(f"no renderer for {name!r} (registered: {known})") from None

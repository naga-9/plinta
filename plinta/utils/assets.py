"""Stylesheets and scripts a package contributes to every page.

A component that ships its own template needs somewhere to put the CSS that
template depends on. Without this it has fields, a template and a config
editor, and no way to be styled — two thirds of an extension point.

    # in the package's AppConfig.ready()
    register_stylesheet("plinta/heatmap/heatmap.css")

Core's own two sheets are not registered: `base.html` links `tokens.css` and
`plinta.css` directly, in a block a consumer can replace wholesale (§10.10).
Registered sheets are drawn **after** them, so a package can rely on the
tokens and the shared primitives already being defined.

**A static path, never a URL.** Core loads nothing from a CDN and neither does
a package registering here; a remote stylesheet is the consumer's own decision
and belongs in the `plinta_css` block where they can see it.

Layer 1, because everything that draws something may need to style it — core
components, contrib packages, and a consumer's own app.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Anything that would make the browser fetch from somewhere else.
REMOTE = ("http://", "https://", "//", "data:")


@dataclass(frozen=True)
class Stylesheet:
    """One registered sheet, and where it sits in the cascade."""

    path: str
    #: Lower is earlier. Ties broken by path, so the order never depends on
    #: which app happened to be imported first.
    order: int = 100


class AssetError(Exception):
    """A stylesheet was registered twice, or names something unusable."""


_registry: dict[str, Stylesheet] = {}


def register_stylesheet(path: str, *, order: int = 100) -> Stylesheet:
    """Add a stylesheet to every page.

        register_stylesheet("plinta/kanban/kanban.css")

    Args:
        path: a path under a static directory, as `{% static %}` wants it.
        order: lower is earlier in the cascade. Core's own sheets are always
            first; 100 is a sensible default for anything that only styles
            its own markup.

    Raises:
        AssetError: the path is empty, remote, or already registered.
    """
    path = (path or "").strip()
    if not path:
        raise AssetError("a stylesheet needs a path")
    if path.startswith(REMOTE):
        raise AssetError(
            f"{path!r} is remote. Load a third-party stylesheet in the "
            "`plinta_css` template block instead, where the choice is visible."
        )
    if path in _registry:
        raise AssetError(f"{path!r} is already registered")
    _registry[path] = Stylesheet(path=path, order=order)
    return _registry[path]


def stylesheets() -> list[Stylesheet]:
    """Every registered sheet, in the order they should be linked."""
    return sorted(_registry.values(), key=lambda s: (s.order, s.path))


@dataclass(frozen=True)
class Script:
    """One registered script, and how it should be loaded."""

    path: str
    order: int = 100
    #: `type="module"`. Modules are deferred by definition.
    module: bool = False
    #: Deferred, which is what nearly everything wants. The exception is a
    #: script that must run before the first paint — a remembered collapse
    #: applied after parsing shows the thing and then takes it away.
    defer: bool = True


_scripts: dict[str, Script] = {}


def register_script(
    path: str, *, order: int = 100, module: bool = False, defer: bool = True
) -> Script:
    """Add a script to every page.

        register_script("plinta/tomselect/adapter.js")

    Loaded after core's own, in `order` then `path`, so a package's glue can
    rely on its vendor being defined.

    Raises:
        AssetError: the path is empty, remote, or already registered.
    """
    path = (path or "").strip()
    if not path:
        raise AssetError("a script needs a path")
    if path.startswith(REMOTE):
        raise AssetError(
            f"{path!r} is remote. Vendor it into your package's static "
            "directory: an install must work offline and under a strict CSP."
        )
    if path in _scripts:
        raise AssetError(f"{path!r} is already registered")
    _scripts[path] = Script(path=path, order=order, module=module, defer=defer)
    return _scripts[path]


def scripts() -> list[Script]:
    """Every registered script, in the order they should be loaded."""
    return sorted(_scripts.values(), key=lambda s: (s.order, s.path))

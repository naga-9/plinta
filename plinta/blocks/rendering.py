"""Turning a Block into HTML.

This module owns the layer boundary that keeps personalisation out of
components: the viewer's `SavedView` delta is merged here, and what reaches a
component is one resolved config that never mentions a saved view.
"""
from __future__ import annotations

from typing import Any

from plinta.blocks.models import Block, SavedView
from plinta.blocks.narrowing import narrowing_for
from plinta.components.base import ComponentConfig, Mode
from plinta.components.registry import find

#: What a block renders when its component type is not installed, or the
#: viewer may not see it. A normal state, not an error.
EMPTY_SLOT = ""


def default_view(block: Block, user) -> SavedView | None:
    """The saved view that applies when the viewer chose none.

    Their own default first, then a public one — a view with no owner. Both
    are marks someone made deliberately; with neither, the block's own config
    applies.

    A public default is how someone holding ``change_savedview`` but not
    ``change_block`` curates a starting view.
    """
    from plinta.permissions import allowed

    if user is None or not getattr(user, "is_authenticated", False):
        return None
    defaults = allowed(user, "view", block.saved_views.filter(is_default=True))
    return (
        defaults.filter(owner=user).first()
        or defaults.filter(owner__isnull=True).first()
    )


def merge(base: dict[str, Any], delta: dict[str, Any] | None) -> dict[str, Any]:
    """The block's config with a saved view's delta over it.

    One level deep: a key the delta sets replaces the block's, and a key it
    omits is inherited. Deep-merging a list would make "show only these three
    columns" impossible to express, since the delta could only ever add.
    """
    return {**(base or {}), **(delta or {})}


def effective_config(block: Block, user, view: SavedView | None = None) -> dict[str, Any]:
    """The config to render this block with, for this viewer.

    Pass ``view`` to apply a chosen one; otherwise the viewer's default applies.
    """
    if view is None:
        view = default_view(block, user)
    return merge(block.config, view.config if view else None)


def resolve(block: Block, user, view: SavedView | None = None) -> ComponentConfig | None:
    """The validated config a component will be called with, or None.

    None means an empty slot: the component type is not installed.
    """
    component = find(block.component_type)
    if component is None:
        return None
    return component.validate(effective_config(block, user, view))


def mode_of(block: Block) -> Mode | None:
    """When this block's data is fetched, or None for an uninstalled component.

    The block's own ``mode`` wins; blank inherits the component's default.
    """
    component = find(block.component_type)
    if component is None:
        return None
    return Mode(block.mode) if block.mode else component.mode


def render_block(
    block: Block,
    user,
    *,
    view: SavedView | None = None,
    extra_filters: dict[str, Any] | None = None,
    **context: Any,
) -> str:
    """Draw ``block`` for ``user``.

    1. Resolve the effective config — the block's, with the viewer's delta over it.
    2. Look up the component. Not registered is an empty slot, not an exception.
    3. Fetch rows and fields through `datasources`, passing the user.
    4. Call the component with the resolved config and the block's narrowing.

    Step 3 is why a block cannot widen access: the narrowing happened below it.

    ``extra_filters`` is resolved filter kwargs from whatever placed the block.
    A page passes its filter bar and the placement's context filter through it.
    """
    from plinta.permissions import can

    if not block.is_active or not can(user, "view", block):
        return EMPTY_SLOT

    component = find(block.component_type)
    if component is None:
        return EMPTY_SLOT

    config = component.validate(effective_config(block, user, view))
    return component.render(
        config,
        user,
        datasource=block.data_source,
        narrow=narrowing_for(block, user, extra_filters),
        block=block,
        **context,
    )

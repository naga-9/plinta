"""Turning a Block into HTML.

This module owns the layer boundary that keeps personalisation out of
components: the viewer's `SavedView` delta is merged here, and what reaches a
component is one resolved config that never mentions a saved view.
"""
from __future__ import annotations

from django.db.models import Q

import logging
from typing import Any

from django.db import models

from django.conf import settings

from plinta.blocks.models import Block, SavedView
from plinta.blocks.narrowing import narrowing_for
from plinta.components.base import ComponentConfig, Mode
from plinta.components.registry import find

logger = logging.getLogger(__name__)

#: What a block renders when its component type is not installed, or the
#: viewer may not see it. A normal state, not an error.
EMPTY_SLOT = ""


class BlockRenderError(Exception):
    """A block could not be drawn.

    Raised in place of whatever went wrong, so a caller drawing several blocks
    can put a message in one slot and carry on with the rest. The original is
    logged with its traceback.
    """

    def __init__(self, block_name: str):
        self.block_name = block_name
        super().__init__(f"{block_name} could not be drawn")


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
    # One query, not one per step: a block has at most a handful of defaults,
    # and asking twice costs a round trip per block on a page.
    defaults = list(
        allowed(user, "view", block.saved_views.filter(is_default=True)).filter(
            models.Q(owner=user) | models.Q(owner__isnull=True)
        )
    )
    mine = [v for v in defaults if v.owner_id == user.pk]
    public = [v for v in defaults if v.owner_id is None]
    return (mine or public or [None])[0]


def views_for(blocks, user) -> dict[int, list[SavedView]]:
    """The saved views this viewer may pick between, per block.

    **One query for the page, not one per block.** A dashboard of eight blocks
    asking separately is eight round trips for a control most of them will not
    draw, and it would make each extra block cost more than the last.

    Own views before shared ones, then by name: a person looks for theirs
    first, and a list ordered by primary key is ordered by nothing.
    """
    from plinta.permissions import allowed

    ids = [block.pk for block in blocks]
    if not ids or user is None or not getattr(user, "is_authenticated", False):
        return {}

    found: dict[int, list[SavedView]] = {}
    for view in allowed(user, "view", SavedView.objects.filter(block_id__in=ids)):
        found.setdefault(view.block_id, []).append(view)

    mine = getattr(user, "pk", None)
    for views in found.values():
        views.sort(key=lambda v: (v.owner_id != mine, v.name))
    return found


def chosen_view(views: list[SavedView], user, asked: str | None) -> SavedView | None:
    """The view in force: the one asked for, else the one that applies.

    Chosen from ``views`` rather than fetched, so it costs no query and a view
    somebody else owns is simply not found — the id is guessable, and a
    refusal would confirm it exists.

    With nothing asked, their own default wins over a public one. Both are
    marks somebody made deliberately; with neither, the block's own config
    applies.
    """
    if asked:
        for view in views:
            if str(view.pk) == str(asked):
                return view
    mine = getattr(user, "pk", None)
    defaults = [v for v in views if v.is_default]
    own = [v for v in defaults if v.owner_id == mine]
    public = [v for v in defaults if v.owner_id is None]
    return (own or public or [None])[0]


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
    extra_filters: Q | None = None,
    **context: Any,
) -> str:
    """Draw ``block`` for ``user``.

    1. Resolve the effective config — the block's, with the viewer's delta over it.
    2. Look up the component. Not registered is an empty slot, not an exception.
    3. Fetch rows and fields through `datasources`, passing the user.
    4. Call the component with the resolved config and the block's narrowing.

    Step 3 is why a block cannot widen access: the narrowing happened below it.

    ``extra_filters`` is a resolved `Q` from whatever placed the block.
    A page passes its filter bar and the placement's context filter through it.
    """
    from plinta.permissions import can

    if not block.is_active or not can(user, "view", block):
        return EMPTY_SLOT

    component = find(block.component_type)
    if component is None:
        return EMPTY_SLOT

    try:
        config = component.validate(effective_config(block, user, view))
        return component.render(
            config,
            user,
            datasource=block.data_source,
            narrow=narrowing_for(block, user, extra_filters),
            block=block,
            **context,
        )
    except Exception:
        # One block must not take down the page holding it — the same reason
        # an uninstalled component degrades. Raised in DEBUG, because a
        # developer wants the traceback, not a tidy card.
        if settings.DEBUG:
            raise
        logger.exception("block %r failed to render", block.name)
        raise BlockRenderError(block.name) from None

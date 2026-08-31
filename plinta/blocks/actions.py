"""What a block's card offers to do with it.

The header's right-hand side: a saved-view picker, an export menu, a "new
record" button, a link to the block's settings. Each is registered by whoever
provides it — `contrib.export` owns its own button, and core's card names no
package that may not be installed.

    register_block_action(
        "export",
        template="plinta/export/button.html",
        permission="plinta_blocks.export_block",
        components={"table_plinta", "table_tabulator"},
        order=20,
    )

The same shape as `register_topbar_item`, with one thing a topbar never needed:
**which components an action applies to.** A column chooser is a table's; an
export is anything with rows; a saved-view picker is anything with a config
worth saving. An action offered on a component that cannot honour it is a
button that does nothing.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

NAME = re.compile(r"[a-z][a-z0-9_]*")


@dataclass(frozen=True)
class BlockAction:
    """One control in a block card's header."""

    name: str
    #: Rendered with the block, the placement and the viewer in context.
    template: str
    #: ``app_label.codename``, or blank for something anyone may do.
    permission: str = ""
    #: Component keys this applies to. Empty means every component.
    components: frozenset[str] = field(default_factory=frozenset)
    #: ``(block, user) -> bool``. The last word, for a condition a permission
    #: cannot express — "this block has saved views to choose between".
    when: Callable[..., bool] | None = None
    order: int = 100

    def applies_to(self, block: Any, user: Any, **context: Any) -> bool:
        """Whether this block, for this viewer, should offer it.

        ``context`` is what the caller already knows — the block's saved
        views, say. Passed in rather than looked up, so a condition costs no
        query: one per block per action is how a dashboard of eight becomes
        forty round trips.
        """
        if self.components and block.component_type not in self.components:
            return False
        if self.permission and not (user and user.has_perm(self.permission)):
            return False
        if self.when is None:
            return True
        try:
            return bool(self.when(block=block, user=user, **context))
        except Exception:  # noqa: BLE001 - a consumer's callable is not ours
            # A condition that fails hides its own action rather than taking
            # the card down with it.
            return False


class BlockActionError(Exception):
    """An action was registered twice, or named unusably."""


_registry: dict[str, BlockAction] = {}


def register_block_action(
    name: str,
    *,
    template: str,
    permission: str = "",
    components: set[str] | None = None,
    when: Callable[..., bool] | None = None,
    order: int = 100,
) -> BlockAction:
    """Add a control to every block card that qualifies.

    Raises:
        BlockActionError: the name is taken, or is not lowercase
            ``[a-z][a-z0-9_]*``.
    """
    if not NAME.fullmatch(name):
        raise BlockActionError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in _registry:
        raise BlockActionError(f"{name!r} is already registered")
    action = BlockAction(
        name=name,
        template=template,
        permission=permission,
        components=frozenset(components or ()),
        when=when,
        order=order,
    )
    _registry[name] = action
    return action


def registered() -> list[BlockAction]:
    """Every action, in display order."""
    return sorted(_registry.values(), key=lambda a: (a.order, a.name))


def actions_for(block: Any, user: Any, **context: Any) -> list[BlockAction]:
    """The actions this block's card should draw for this viewer."""
    return [a for a in registered() if a.applies_to(block, user, **context)]

"""Editing one block's config: the same settings, one layer lower.

The saved-view editor draws a delta over a block. The inspector draws the
block itself, and what sits beneath it is the **schema's own defaults**. So a
blank control means "the component's default" here and "same as the block"
there, and both are the one mechanism in `blocks.settings` (§12.3).

**Not the write pipeline.** `Block` is a configuration model and is not
registered as a DataSource (§6.1b), so it carries no field permissions and
there is nothing per-field for `authorise` to check. It is gated whole by the
model permission and its row policy, which is what `can(user, "change", block)`
answers — the same reasoning the Data Sources screen follows (§12.1).
"""
from __future__ import annotations

from typing import Any

from plinta.blocks.models import Block


def visible_blocks(user):
    """The blocks this viewer may see: theirs, and the public ones."""
    from plinta.permissions import allowed

    return allowed(user, "view", Block.objects.select_related("data_source"))


def settings_for(component, block: Block, user) -> list[dict[str, Any]]:
    """The inspector's controls, over the schema's defaults."""
    from plinta.blocks import settings

    stored = block.config or {}
    return settings.settings_for(
        component, block, user, base={}, stored=stored, effective=stored
    )


def save_config(block: Block, user, post) -> dict[str, list[str]]:
    """Store what the settings form submitted, or return its errors.

    Returns ``{}`` on success and ``{field: [messages]}`` otherwise, the shape
    `plinta.forms.parse` already speaks — so a caller renders the same
    controls back with the messages beside them.
    """
    from django.core.exceptions import ValidationError

    from plinta.blocks import settings
    from plinta.components.registry import find
    from plinta.forms.parse import parse

    component = find(block.component_type)
    if component is None:
        # An unregistered component cannot judge its own config, the same
        # reason it renders an empty slot rather than failing (§7.2).
        return {"_general": [f"{block.component_type!r} is not registered."]}

    schema = component.config_schema
    asked = settings.submitted(schema, post)
    config, errors = parse(schema, asked)
    if errors:
        return errors

    # `parse` returns the **resolved** config, every default filled in. Stored
    # whole, that is a copy of the component's defaults at this moment: the
    # component later changes one, and the block still says the old value with
    # nothing to indicate why. The same fork ADR 0004 refuses for a saved
    # view, one layer down. So only what was actually submitted is kept, and
    # the coercion `parse` did on it is what makes this worth going through.
    block.config = {name: value for name, value in config.items() if name in asked}
    try:
        block.full_clean()
    except ValidationError as exc:
        return dict(exc.message_dict)
    block.save()
    return {}


def duplicate(block: Block, user) -> Block:
    """A copy of ``block``, owned by whoever asked for it.

    Owned rather than public: copying somebody's block is how you start from
    their work, and publishing the result is a separate decision.
    """
    copy = Block(
        name=_free_name(block.name, user),
        component_type=block.component_type,
        data_source=block.data_source,
        config=dict(block.config or {}),
        base_filter=dict(block.base_filter or {}),
        queryset_modifier=block.queryset_modifier,
        mode=block.mode,
        description=block.description,
        icon=block.icon,
        owner=user,
    )
    copy.save()
    return copy


def _free_name(name: str, user) -> str:
    """``name`` with a suffix that does not collide for this owner.

    A block's name is unique per owner, so a copy needs its own; numbered
    rather than random, because the name is what somebody reads in the
    catalogue.
    """
    taken = set(
        Block.objects.filter(owner=user).values_list("name", flat=True)
    )
    candidate = f"{name}-copy"
    suffix = 2
    while candidate in taken:
        candidate = f"{name}-copy-{suffix}"
        suffix += 1
    return candidate[:100]

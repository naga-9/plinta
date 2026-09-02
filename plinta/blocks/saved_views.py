"""Editing a saved view: the inverse of the merge that renders one.

`effective_config` merges a view's delta over its block's config. This turns a
submitted form back into a delta — which is the whole difficulty, because a
form posts every field and a delta must hold only the ones somebody meant to
change.

**Deltas remain deltas, never copies** (ADR 0004). A view storing a full copy
freezes its block at the moment it was saved: the author later fixes a default
`page_size` or a `sort`, sees it work on their own screen, and every saved view
still shows the old one with nothing to indicate why. The fork happens at save
time and surfaces months later.

The columns are the exception that proves it. `columns` is the field a view
almost always overrides, so a column added to the DataSource does **not**
appear in an existing view — which is correct, and is why the editor offers it
as an unchecked row rather than adding it. Override what you chose, inherit
what you did not.
"""
from __future__ import annotations

from typing import Any

from plinta.blocks.models import SavedView

def delta(
    submitted: dict[str, Any],
    base: dict[str, Any],
    pinned: set[str] | None = None,
) -> dict[str, Any]:
    """The overrides in ``submitted``: what differs from ``base``.

    A field equal to the block's value is dropped rather than stored, so a
    control left showing what the block says leaves the view inheriting it,
    and a later change to the block still reaches here. **A blank control is
    simply absent from ``submitted``** — that is the whole of "same as the
    block", and there is nothing else to operate.

    ``pinned`` is stored whatever it equals. A list has no blank: an empty one
    is a real answer, not an absent one, so "the columns I chose" cannot be
    told from "I chose none" and a view's columns must be its own. It is also
    what makes a column added to the DataSource later stay out of a view saved
    before it.
    """
    pinned = pinned or set()
    return {
        name: value
        for name, value in submitted.items()
        if name in pinned or value != base.get(name)
    }


def inherited(config: dict[str, Any], base: dict[str, Any]) -> set[str]:
    """The fields this view does **not** override.

    What the editor draws as "same as the block": the value comes from there,
    and changing the block changes it here.
    """
    return {name for name in base if name not in config}


def visible_views(block, user) -> list[SavedView]:
    """The views on ``block`` this viewer may see, theirs and the public ones."""
    from plinta.permissions import allowed

    return list(allowed(user, "view", block.saved_views.all()))


def may_publish(user) -> bool:
    """Whether this viewer may make a view everyone sees.

    `owner = None` is public, so publishing is a change to one field — and a
    field permission is the only thing that can gate one (§6.1b). Without the
    DataSource registration this question has no answer and everybody
    publishes.
    """
    return user.has_perm("plinta_blocks.change_savedview_owner")


def may_default(user) -> bool:
    """Whether this viewer may mark a view as one to open on.

    For **drawing** the control. The write pipeline is what enforces it — the
    same split the record form uses, where `writable_fields` decides what is
    offered and `authorise` decides what is taken.
    """
    return user.has_perm("plinta_blocks.change_savedview_is_default")


def save(
    block,
    user,
    *,
    name: str,
    values: dict[str, Any],
    view: SavedView | None = None,
    public: bool = False,
    default: bool = False,
    pinned: set[str] | None = None,
) -> SavedView:
    """Create or update a view over ``block``, storing only what differs.

    Written through the **pipeline**, not saved directly, so the permissions
    are the ones every other write uses: the model permission, the row policy,
    and a field permission for each field being changed. Publishing is then
    not a special case — it is a change to `owner`, and
    `change_savedview_owner` gates it because it gates that field.

    A field is only submitted when it **changes**, which is what makes that
    work: setting a view as your own default asks for
    `change_savedview_is_default`, and saving one that was already the default
    does not.

    Raises:
        WriteDenied: the viewer may not make this change.
        ValidationError: the model refused it — a duplicate name, say.
    """
    from plinta.blocks.write import write

    instance = view or SavedView(block=block, owner=user)
    changing: dict[str, Any] = {
        "name": name,
        "config": delta(values, block.config or {}, pinned),
    }
    # Only when it moves. Owning a view you just made is not "changing the
    # owner"; publishing one is, which is why the permission lands there.
    if public != (instance.owner_id is None):
        changing["owner"] = None if public else user
    if default != instance.is_default:
        changing["is_default"] = default

    saved, _ = write(instance, changing, user, source="view editor")
    return saved


def settings_for(
    component, block, user, view: SavedView | None
) -> list[dict[str, Any]]:
    """The view editor's fields, over the block's config.

    The same mechanism the block inspector uses, with the block beneath rather
    than the schema's defaults (§12.3) — so here a blank control means *same
    as the block*.
    """
    from plinta.blocks import settings

    base = block.config or {}
    stored = (view.config if view else None) or {}
    return settings.settings_for(
        component,
        block,
        user,
        base=base,
        stored=stored,
        effective={**base, **stored},
    )


def column_choices(block, user, view: SavedView | None = None) -> list[dict[str, Any]]:
    """Every column this viewer may see, in the order this view shows them.

    Read from the **effective** config, because the editor is editing a view:
    reading the block's order would show the author's arrangement to somebody
    who had already made their own.
    """
    from plinta.blocks import settings

    stored = (view.config if view else None) or {}
    return settings.column_choices(block, user, {**(block.config or {}), **stored})


def of_kind(choices: list, kinds: tuple) -> list:
    """``choices`` narrowed to the kinds a setting admits."""
    from plinta.blocks import settings

    return settings.of_kind(choices, kinds)


def submitted_settings(schema, post) -> dict[str, Any]:
    """What the view editor is asking to store; a blank scalar is absent."""
    from plinta.blocks import settings

    return settings.submitted(schema, post)


def pinned_settings(schema) -> set[str]:
    """The settings a view always stores, blank or not."""
    from plinta.blocks import settings

    return settings.pinned(schema)

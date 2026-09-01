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

#: Set on a submitted field to mean "stop overriding this". Without it a form
#: can only ever add overrides, and a view drifts into a copy one save at a
#: time — which is the failure this module exists to prevent.
INHERIT = "__inherit__"


def delta(submitted: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    """The overrides in ``submitted``: what differs from ``base``.

    A field equal to the block's value is dropped rather than stored, so
    setting a control to the value it already shows leaves the view inheriting
    it — and a later change to the block still reaches this view.
    """
    return {
        name: value
        for name, value in submitted.items()
        if value != INHERIT and value != base.get(name)
    }


def inherited(config: dict[str, Any], base: dict[str, Any]) -> set[str]:
    """The fields this view does **not** override.

    What the editor draws as "inherited": the value comes from the block, and
    changing the block changes it here.
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


def save(
    block,
    user,
    *,
    name: str,
    values: dict[str, Any],
    view: SavedView | None = None,
    public: bool = False,
) -> SavedView:
    """Create or update a view over ``block``, storing only what differs.

    Raises:
        PermissionError: publishing without `change_savedview_owner`. A
            personal view needs nothing beyond seeing the block.
    """
    if public and not may_publish(user):
        raise PermissionError("may not publish a view to everyone")

    owner = None if public else user
    config = delta(values, block.config or {})

    if view is None:
        return SavedView.objects.create(
            block=block, name=name, owner=owner, config=config
        )
    view.name = name
    view.config = config
    if public != (view.owner_id is None):
        # Changing who owns it is the publish, and is gated above.
        view.owner = owner
    view.save()
    return view


def controls(component, block, user, view: SavedView | None) -> list[dict[str, Any]]:
    """The view editor's fields, derived from the component's own schema.

    Nothing here knows what a table is. A consumer's component declares a
    config schema and gets an editor for it, which is what `plinta.forms` was
    built for — and why a component overriding one field (`columns` is the
    obvious one) registers a widget rather than a whole form.

    Each field carries whether this view **overrides** it. That is the
    difference between a delta and a copy: a control showing 25 because the
    block says 25 must be told apart from one showing 25 because somebody
    chose it, or the first save turns every inherited field into an override.
    """
    from plinta.forms.fields import fields_for
    from plinta.forms.overrides import overrides_for

    schema = component.config_schema
    base = block.config or {}
    stored = (view.config if view else None) or {}
    effective = {**base, **stored}

    drawn = []
    for field in fields_for(schema, overrides=overrides_for(schema)):
        drawn.append(
            {
                "name": field.name,
                "label": field.title or field.name.replace("_", " ").capitalize(),
                "widget": field.widget,
                "template": field.override_template,
                "help": field.description or "",
                "value": effective.get(field.name, field.default),
                # What the block would give it, shown beside an override so
                # "back to inherited" says what it goes back to.
                "inherited_value": base.get(field.name, field.default),
                "overridden": field.name in stored,
            }
        )
    return drawn


def column_choices(block, user, view: SavedView | None = None) -> list[dict[str, Any]]:
    """Every column this viewer may see, in the order this view shows them.

    Chosen ones first and in their order, then the rest unchecked — so a
    column added to the DataSource after a view was saved appears as
    something to select rather than something that appeared.

    Read from the **effective** config, because the editor is editing a view:
    reading the block's order would show the author's arrangement to somebody
    who had already made their own.
    """
    from plinta.datasources.services import get_available_fields

    available = {f.field_name: f for f in get_available_fields(block.data_source, user)}
    effective = {**(block.config or {}), **((view.config if view else None) or {})}
    chosen = [name for name in effective.get("columns") or [] if name in available]
    return [
        {"name": name, "label": available[name].label or name, "chosen": chosen_flag}
        for name, chosen_flag in (
            [(n, True) for n in chosen]
            + [(n, False) for n in available if n not in chosen]
        )
    ]

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

    `is_default` is a field, so a field permission is what gates it — the same
    mechanism as publishing, and the reason `SavedView` is registered as a
    DataSource at all (§6.1b).
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

    ``default`` marks it the one to open on. Which default that is follows
    ``public``: a shared view's is everyone's, a personal view's is this
    viewer's own. One field, two meanings, decided by who owns the row — and
    the model keeps at most one of each.

    Raises:
        PermissionError: publishing without `change_savedview_owner`, or
            defaulting without `change_savedview_is_default`. A personal view
            that is neither needs nothing beyond seeing the block.
    """
    if public and not may_publish(user):
        raise PermissionError("may not publish a view to everyone")
    if default and not may_default(user):
        raise PermissionError("may not set a default view")

    owner = None if public else user
    config = delta(values, block.config or {}, pinned)

    if view is None:
        return SavedView.objects.create(
            block=block, name=name, owner=owner, config=config,
            is_default=default,
        )
    view.name = name
    view.config = config
    view.is_default = default
    if public != (view.owner_id is None):
        # Changing who owns it is the publish, and is gated above.
        view.owner = owner
    view.save()
    return view


def settings_for(
    component, block, user, view: SavedView | None
) -> list[dict[str, Any]]:
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

    drawn = []
    for field in fields_for(schema, overrides=overrides_for(schema)):
        fallback = base.get(field.name, field.default)
        # A container has no blank, so it is always the view's own and shows
        # the effective value. A scalar shows only its *override*, with the
        # block's value behind it as a placeholder — empty means inherited,
        # which is the whole mechanism.
        pinned = field.widget == "json"
        drawn.append(
            {
                "name": field.name,
                "label": field.title or field.name.replace("_", " ").capitalize(),
                "widget": field.widget,
                "choices": field.choices,
                "template": field.override_template,
                "help": field.description or "",
                "pinned": pinned,
                "value": (
                    stored.get(field.name, fallback)
                    if pinned
                    else stored.get(field.name)
                ),
                # What the block gives it, drawn as the placeholder or as the
                # first option of a select — so a control says where its
                # value comes from without a second control to explain it.
                "inherited_value": fallback,
                "overridden": field.name in stored,
            }
        )

    # The two mechanisms that need more than a value: a chooser needs the
    # columns this viewer may see, and a builder needs its rows.
    available = column_choices(block, user, view)
    for setting in drawn:
        if setting["widget"] == "column":
            setting["columns"] = available
        elif setting["name"] == "columns":
            setting["columns"] = available
        elif setting["name"] == "sort":
            setting["columns"] = available
            setting["rows"] = [
                {"field": row.get("field", ""), "direction": row.get("direction", "asc")}
                for row in (setting["value"] or [])
                if isinstance(row, dict)
            ]
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
    named = [name for name in effective.get("columns") or [] if name in available]
    # An empty list means *every visible column* to `choose_columns`, not
    # none — so a chooser opened on it must show them ticked. Opened empty,
    # saving would post nothing, store an empty list, and the view would then
    # pick up every column added afterwards: the opposite of pinning.
    chosen = named or [
        name for name, field in available.items() if getattr(field, "visible", True)
    ]
    return [
        {"name": name, "label": available[name].label or name, "chosen": chosen_flag}
        for name, chosen_flag in (
            [(n, True) for n in chosen]
            + [(n, False) for n in available if n not in chosen]
        )
    ]


def submitted_settings(schema, post) -> dict[str, Any]:
    """What a settings form is asking to store.

    A **blank scalar is absent**, which is how "same as the block" reaches
    here without a control of its own. A container is read whatever it holds,
    because a list has no blank — an empty one is a real answer.

    The two builders post their own shape: a column chooser posts the names it
    ticked in the order they appear, and a sort builder posts two parallel
    lists, which is what a browser sends for repeated controls.
    """
    from plinta.forms.fields import widget_for

    values: dict[str, Any] = {}
    for name, info in schema.model_fields.items():
        widget = widget_for(info.annotation)

        if name == "columns":
            values[name] = post.getlist("columns")
            continue
        if name == "sort":
            fields = post.getlist("sort_field")
            directions = post.getlist("sort_direction")
            values[name] = [
                {"field": field, "direction": direction or "asc"}
                for field, direction in zip(fields, directions)
                if field
            ]
            continue
        if widget == "json":
            # Another container, with no builder: it arrives as JSON text.
            raw = post.get(name, "")
            if raw:
                values[name] = raw
            continue

        raw = post.get(name, "")
        if raw == "":
            continue  # same as the block
        values[name] = raw
    return values


def pinned_settings(schema) -> set[str]:
    """The settings a view always stores, blank or not.

    Containers: a list has no blank state, so "the columns I chose" cannot be
    told from "I chose none". Storing them always is also what keeps a column
    added to the DataSource later out of a view saved before it.
    """
    from plinta.forms.fields import widget_for

    return {
        name
        for name, info in schema.model_fields.items()
        if widget_for(info.annotation) == "json"
    }

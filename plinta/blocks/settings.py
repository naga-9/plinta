"""Drawing and reading a component's settings, over whatever sits beneath.

Two screens edit the same settings, and they differ only in what "blank"
inherits from:

    the **saved-view editor** — the block's config is beneath, so a blank
    control means *same as the block*

    the **block inspector** — nothing is beneath but the schema's own
    defaults, so a blank control means *the component's default*

That is one mechanism with two bases, not two mechanisms. `settings_for` takes
the base and the stored layer explicitly; each screen says which is which.

Nothing here knows what a table is. A consumer's component declares a config
schema and gets an editor for it, which is what `plinta.forms` was built for —
and why a component overriding one field registers a widget rather than a
whole form (§12.3).
"""
from __future__ import annotations

from typing import Any


def settings_for(
    component,
    block,
    user,
    *,
    base: dict[str, Any],
    stored: dict[str, Any],
    effective: dict[str, Any],
) -> list[dict[str, Any]]:
    """The controls to draw, one per field of the component's config schema.

    Each carries whether ``stored`` **overrides** it. That is the difference
    between a delta and a copy: a control showing 25 because the base says 25
    must be told apart from one showing 25 because somebody chose it, or the
    first save turns every inherited field into an override.

    ``effective`` is what the screen currently renders with — the merge of
    both layers — and decides which columns a chooser shows as chosen.
    """
    from plinta.forms.fields import fields_for
    from plinta.forms.overrides import overrides_for

    schema = component.config_schema
    drawn = []
    for field in fields_for(schema, overrides=overrides_for(schema)):
        fallback = base.get(field.name, field.default)
        # A container has no blank, so it is always the screen's own and shows
        # the effective value. A scalar shows only its *override*, with the
        # value beneath it as a placeholder — empty means inherited, which is
        # the whole mechanism.
        pinned = field.widget == "json"
        drawn.append(
            {
                "name": field.name,
                "label": field.title or field.name.replace("_", " ").capitalize(),
                "widget": field.widget,
                "choices": field.choices,
                "kinds": field.kinds,
                "template": field.override_template,
                "help": field.description or "",
                "pinned": pinned,
                "value": (
                    stored.get(field.name, fallback)
                    if pinned
                    else stored.get(field.name)
                ),
                # What sits beneath it, drawn as the placeholder or as the
                # first option of a select — so a control says where its
                # value comes from without a second control to explain it.
                "inherited_value": fallback,
                "overridden": field.name in stored,
            }
        )

    # The two mechanisms that need more than a value: a chooser needs the
    # columns this viewer may see, and a builder needs its rows.
    available = column_choices(block, user, effective)
    for setting in drawn:
        if setting["widget"] == "column":
            setting["columns"] = of_kind(available, setting["kinds"])
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


def of_kind(choices: list, kinds: tuple) -> list:
    """``choices`` narrowed to the kinds a setting admits.

    Empty ``kinds`` offers everything, which is right for a link: any column
    can carry one. A setting that will be summed says ``("number",)``, because
    offered a title it returns zero — worse than an error, since nothing says
    anything is wrong.
    """
    if not kinds:
        return choices
    return [choice for choice in choices if choice["kind"] in kinds]


def column_choices(block, user, effective: dict[str, Any]) -> list[dict[str, Any]]:
    """Every column this viewer may see, in the order ``effective`` shows them.

    Chosen ones first and in their order, then the rest unchecked — so a
    column added to the DataSource after a view was saved appears as something
    to select rather than something that appeared.

    A block with no DataSource has no columns: a content component such as
    `text` carries its own content in config, and asking it for columns is a
    question about a model it does not have.
    """
    from plinta.datasources.kinds import kind_of
    from plinta.datasources.services import get_available_fields

    if block.data_source is None:
        return []

    available = {f.field_name: f for f in get_available_fields(block.data_source, user)}
    named = [name for name in effective.get("columns") or [] if name in available]
    # An empty list means *every visible column* to `choose_columns`, not
    # none — so a chooser opened on it must show them ticked. Opened empty,
    # saving would post nothing, store an empty list, and the view would then
    # pick up every column added afterwards: the opposite of pinning.
    chosen = named or [
        name for name, field in available.items() if getattr(field, "visible", True)
    ]
    model = block.data_source.model
    return [
        {
            "name": name,
            "label": available[name].label or name,
            "chosen": chosen_flag,
            # What it holds, so a setting can say which kinds it admits. A
            # computed column resolves to no model field, so its own `sorter`
            # is the fallback — which is the work `sorter` still does there.
            "kind": kind_of(
                model, name, getattr(available[name], "sorter", "") or "string"
            ),
        }
        for name, chosen_flag in (
            [(n, True) for n in chosen]
            + [(n, False) for n in available if n not in chosen]
        )
    ]


def submitted(schema, post) -> dict[str, Any]:
    """What a settings form is asking to store.

    A **blank scalar is absent**, which is how "same as what is beneath"
    reaches here without a control of its own. A container is read whatever it
    holds, because a list has no blank — an empty one is a real answer.

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
            continue  # same as what is beneath
        values[name] = raw
    return values


def pinned(schema) -> set[str]:
    """The settings a screen always stores, blank or not.

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

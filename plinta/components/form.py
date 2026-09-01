"""The form component.

Core's reference implementation of the **write** contract, as `table_plinta` is
of the read one (ADR 0005). A write path with no writing component in core is
a contract nobody dogfoods — the same argument that put a table there.

Not `plinta.forms`, which derives a form from a **pydantic schema** and exists
to edit a block's configuration. This edits a *record*, so its fields come
from the DataSource and the model behind it, and the two never meet.

It writes through the same endpoint a dragged card and an edited cell use: one
row and the fields being written (§8.11). The form is the case that sends
several at once, which is the whole reason the shape was fixed before the
table was wired to it.
"""
from __future__ import annotations

from typing import Any

from django.template.loader import render_to_string
from pydantic import Field

from plinta.components.base import Component, ComponentConfig, Mode, Padding
from plinta.components.registry import register_component

#: What each kind is edited with. A control per kind and no registry yet: a
#: registry with one implementation is a guess about the second one.
CONTROLS = {
    "string": "text",
    "number": "number",
    "boolean": "checkbox",
    "date": "date",
    "datetime": "datetime-local",
    "time": "time",
    "relation": "select",
    "relations": "select-multiple",
}


class FormConfig(ComponentConfig):
    """A form's stored configuration.

    Which fields appear is **not** freely chosen here either: `columns` may
    order and narrow what the DataSource offers, and nothing it names that the
    viewer may not write will be drawn.
    """

    #: What the button says. A form for one thing should say what it does.
    submit_label: str = Field(default="Save")
    #: Shown once a write lands, so a save that changed nothing visible still
    #: says it happened.
    saved_text: str = Field(default="Saved")


@register_component("form_plinta", label="Form")
class FormComponent(Component):
    """One record's editable fields, written together.

    **Requires JavaScript**, unlike core's table. The write endpoint takes
    `application/json` and nothing else (§15.3), so a plain form post has
    nowhere to go — the alternative was a second write entry point parsing a
    second content type, which is the duplication the one endpoint exists to
    prevent. Worth recording as the cost it is.
    """

    config_schema = FormConfig
    #: The controls are drawn on the server; there is nothing to fetch.
    mode = Mode.INLINE
    supported_modes = frozenset({Mode.INLINE})
    #: It writes, which is the point.
    writes = True
    #: Room to read, unlike a table whose cells carry their own padding.
    padding = Padding.DEFAULT

    def fields_for(self, config: FormConfig, user, *, datasource) -> list:
        """The columns this viewer may write, in the order the config asks.

        Writable and not merely visible: a form drawing a field the save would
        refuse is a promise it cannot keep, and the writer only finds out
        after typing.
        """
        from plinta.datasources.services import writable_fields

        allowed = writable_fields(datasource, user)
        chosen = [name for name in (config.columns or []) if name in allowed]
        return [allowed[name] for name in (chosen or sorted(allowed))]

    def control(self, field: Any, record: Any, kind: str, options: list) -> dict:
        """One field, as the template draws it."""
        from plinta.renderers.values import raw

        return {
            "name": field.field_name,
            "label": field.label or field.field_name,
            "kind": kind,
            "control": CONTROLS.get(kind, "text"),
            "value": raw(record, field.field_name, kind) if record else None,
            "options": options,
            "help": getattr(field, "help_text", "") or "",
        }

    def render(self, config: FormConfig, user, **context: Any) -> str:
        """The controls, and the record they are about.

        No record is a create, which is the same form with nothing in it.
        """
        from plinta.datasources.choices import picker_for
        from plinta.datasources.kinds import kind_of
        from plinta.utils.styles import classes

        datasource = context["datasource"]
        model = datasource.model
        record = context.get("record")
        if record is not None and not isinstance(record, model):
            # A detail page about something else. Its record is not ours to
            # edit, and drawing it filled in would be a lie about what saving
            # would change.
            record = None

        controls = []
        for field in self.fields_for(config, user, datasource=datasource):
            kind = kind_of(model, field.field_name, "string")
            drawn = picker_for(field, model, user) if kind.startswith("relation") else {}
            controls.append(
                self.control(field, record, kind, drawn.get("options") or [])
            )

        return render_to_string(
            "plinta/components/form.html",
            {
                # Rendered without a request, so the class map the context
                # processor would supply is passed in — a style pack renames
                # a form the same way it renames everything else.
                "cls": classes(),
                "controls": controls,
                "record": getattr(record, "pk", None),
                "config": config,
                "write_url": context.get("write_url", ""),
                "options_url": context.get("options_url", ""),
            },
        )

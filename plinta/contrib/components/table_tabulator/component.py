"""A table Tabulator draws.

The same capability as core's `table_plinta`, with a vendor behind it and the
interaction that buys: sorting and filtering in the browser, remote paging
through fifty thousand rows, resizable columns.

`capability_implementation`, so it sits beside `table_plinta` and neither is
privileged. Switching a block from one to the other is a change of
`component_type`, and the new component's default mode comes with it — mode
says *when the data arrives*, never which widget draws it (§7.3).
"""
from __future__ import annotations

import json
from typing import Any

from django.utils.html import format_html
from django.utils.safestring import mark_safe

from plinta.components.base import Component, Mode, Padding
from plinta.components.registry import register_component
from plinta.components.tabular import TabularConfig


class TabulatorConfig(TabularConfig):
    """What a Tabulator table may be told.

    Deliberately not `TableConfig`: the two components draw differently, so a
    block moving between them is validated at save like any other config
    change rather than silently keeping keys the new one ignores.
    """

    #: `page_size` and `sort` come from `TabularConfig`.
    #: CSS length. Tabulator needs a height to page inside; blank fills the card.
    height: str = ""
    #: A filter box under each column that declares itself filterable.
    header_filters: bool = False
    #: Columns the viewer may drag wider.
    resizable: bool = True
    #: What it says when nothing matched.
    empty_text: str = ""
    #: Whether cells may be edited in place. Off by default: a table is a way
    #: of reading until somebody says otherwise, and a grid that saves on blur
    #: is a surprising thing to get by accident.
    editable: bool = False
    #: A pencil on each row, opening the record's form in a dialog. Separate
    #: from `editable`: editing a cell where it sits and opening the whole
    #: record are different gestures, and a table may reasonably offer one,
    #: both or neither.
    row_form: bool = False
    #: Which registered layout that form uses. A name and not a nested form
    #: config: a component says *which* form to open, and what a form is
    #: remains the form's own business.
    form_layout: str = ""


@register_component("table_tabulator", label="Table (interactive)")
class TabulatorComponent(Component):
    """Rows and columns, drawn by Tabulator.

    **Fetch by default**, because that is what the vendor is for: a grid the
    client sorts and pages needs the server to answer for a page at a time,
    and a ten-thousand-row table cannot be inlined. A block may override to
    `inline` — Tabulator's own `paginationMode: 'local'` — which is what a
    five-row related grid on a detail page wants.
    """

    config_schema = TabulatorConfig
    mode = Mode.FETCH
    #: Both, and the adapter reads which it was given: rows in the payload mean
    #: local paging, their absence means remote.
    supported_modes = frozenset({Mode.INLINE, Mode.FETCH})
    #: Tabulator draws its own cell padding and its own borders.
    padding = Padding.NONE
    #: A cell can be edited in place. Which cells is per viewer and comes with
    #: the columns; whether this viewer may is the server's answer, given
    #: again when the write arrives.
    writes = True

    def render(self, config: TabulatorConfig, user, **context: Any) -> str:
        """A mount point, and the payload beside it.

        Fetch mode sends config alone and the client asks for rows. Inline
        sends the first page with it, so nothing is requested at all — the
        same mount, told a different amount.
        """
        payload: dict[str, Any] = {"config": config.model_dump()}

        if self.mode == Mode.INLINE or context.get("mode") == Mode.INLINE:
            from plinta.blocks.feed import feed

            payload.update(
                feed(
                    self,
                    config,
                    user,
                    datasource=context["datasource"],
                    narrow=context.get("narrow"),
                    asked={"page": 1, "size": config.page_size, "sort": [],
                           "filters": {}, "view": ""},
                )
            )

        return format_html(
            '<div class="pl-tabulator" data-plinta-mount="table_tabulator" '
            'data-plinta-url="{}" data-plinta-write-url="{}" '
            'data-plinta-options-url="{}" data-plinta-form-url="{}" '
            'style="{}">'
            '<script type="application/json">{}</script></div>',
            context.get("data_url", ""),
            context.get("write_url", "") if config.editable else "",
            context.get("options_url", "") if config.editable else "",
            context.get("form_url", "") if config.row_form else "",
            f"height: {config.height}" if config.height else "",
            # `</script>` inside a string would close the tag it sits in.
            mark_safe(
                json.dumps(payload)
                .replace("<", "\\u003c")
                .replace(">", "\\u003e")
                .replace("&", "\\u0026")
            ),
        )

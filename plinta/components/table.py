"""The table component.

The only one core ships. Every other component registers through the same door
a third party would use (ADR 0005), so the contract is dogfooded rather than
asserted.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from plinta.components.base import Component, ComponentConfig, Mode
from plinta.components.registry import register_component
from plinta.renderers.registry import get as get_renderer


class Sort(ComponentConfig):
    """One ordering, applied in the order the list gives them."""

    field: str
    direction: Literal["asc", "desc"] = "asc"


class TableConfig(ComponentConfig):
    """A table's stored configuration.

    Which columns appear is **not** here: that comes from the DataSource's
    fields, narrowed by field permission. Config that could name a column the
    viewer may not see would be a second answer to a question `datasources`
    already answers.
    """

    title: str = ""
    page_size: int = Field(default=50, gt=0)
    sort: list[Sort] = Field(default_factory=list)
    #: CSS length, passed through to the widget. Empty lets it decide.
    height: str = ""
    #: A column whose value links to the row's detail page.
    row_link_field: str = ""


@register_component("table", label="Table")
class TableComponent(Component):
    """Rows and columns, sorted and paged by the client."""

    config_schema = TableConfig
    #: The client sorts, filters and pages, and a large table cannot be inlined.
    mode = Mode.FETCH

    def get_data(self, config: TableConfig, user, *, datasource, narrow=None):
        """The base rows and fields, ordered as the config asks."""
        rows, fields = super().get_data(
            config, user, datasource=datasource, narrow=narrow
        )
        ordering = [
            f"-{s.field}" if s.direction == "desc" else s.field for s in config.sort
        ]
        if ordering:
            rows = rows.order_by(*ordering)
        return rows, fields

    def render(self, config: TableConfig, user, **context: Any) -> str:
        """Draw the table through the renderer for the asked-for format.

        Defaults to HTML, and substitutes HTML for a format nothing registered
        (§7.1), so a caller never asks whether `contrib.export` is installed.
        """
        rows, fields = self.get_data(
            config,
            user,
            datasource=context["datasource"],
            narrow=context.get("narrow"),
        )
        renderer = get_renderer(context.get("format", "html"))
        return renderer.render(rows, fields, config.model_dump(), user)

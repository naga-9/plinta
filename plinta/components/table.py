"""The table component.

The only one core ships, and it carries no vendor: a grid library is an
opinion about how a table behaves, and one in core would make every consumer
either accept it or fight it. Every other component registers through the same
door a third party would use (ADR 0005), so the contract is dogfooded rather
than asserted.
"""
from __future__ import annotations

from typing import Any, Literal

from django.core.paginator import Page, Paginator
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
    """Rows and columns, rendered on the server.

    No grid library. Sorting, paging and filtering are the server's, reached by
    ordinary links and the page's filter bar, so a viewer needs no JavaScript.
    A consumer wanting client-side sorting, column resizing or inline cell
    editing installs `datagrid`, or registers their own component.
    """

    config_schema = TableConfig
    #: The rows are in the HTML, so there is nothing to fetch.
    mode = Mode.INLINE
    #: And nothing to fetch it with: there is no client adapter for a table
    #: the server already drew. A block asking for `fetch` is refused when it
    #: is saved rather than rendering nothing.
    supported_modes = frozenset({Mode.INLINE})

    def get_data(self, config: TableConfig, user, *, datasource, narrow=None):
        """The base rows and fields, ordered as the config asks."""
        rows, fields = super().get_data(
            config, user, datasource=datasource, narrow=narrow
        )
        ordering = [
            f"-{s.field}" if s.direction == "desc" else s.field for s in config.sort
        ]
        if ordering:
            return rows.order_by(*ordering), fields
        if not rows.ordered:
            # Paging an unordered queryset is not merely untidy: the database
            # may return rows in a different order for each LIMIT/OFFSET, so a
            # row can appear on two pages and another on none.
            return rows.order_by("pk"), fields
        return rows, fields

    def page(self, rows, config: TableConfig, number: int = 1) -> Page:
        """One page of ``rows``, and what a pager needs to draw itself.

        Django's `Paginator`, so an out-of-range or unparseable page number
        lands on the last page rather than raising on a link someone typed.
        """
        paginator = Paginator(rows, config.page_size)
        return paginator.get_page(number)

    def render(self, config: TableConfig, user, **context: Any) -> str:
        """Draw one page of the table, in the asked-for format.

        Substitutes HTML for a format nothing registered (§7.1), so a caller
        never asks whether `contrib.export` is installed.

        **Rendering is paged; `get_data` is not.** A screen draws `page_size`
        rows however many the query matches, which is what lets a
        server-rendered table hold fifty thousand. An export wants every row
        and calls `get_data` itself.
        """
        rows, fields = self.get_data(
            config,
            user,
            datasource=context["datasource"],
            narrow=context.get("narrow"),
        )
        page = self.page(rows, config, context.get("page", 1))
        renderer = get_renderer(context.get("format", "html"))
        return renderer.render(page.object_list, fields, config.model_dump(), user)

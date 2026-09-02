"""The table component.

The only one core ships, and it carries no vendor: a grid library is an
opinion about how a table behaves, and one in core would make every consumer
either accept it or fight it. Every other component registers through the same
door a third party would use (ADR 0005), so the contract is dogfooded rather
than asserted.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from django.core.paginator import Page

from plinta.components.base import Component, Mode, Padding
from plinta.components.registry import register_component
from plinta.components.tabular import Sort, TabularConfig, ordered, paged, sort_asked
from plinta.renderers.registry import get as get_renderer

__all__ = ["Sort", "TableComponent", "TableConfig"]


class TableConfig(TabularConfig):
    """A table's stored configuration.

    Which columns appear is **not** here: that comes from the DataSource's
    fields, narrowed by field permission. Config that could name a column the
    viewer may not see would be a second answer to a question `datasources`
    already answers.
    """

    # A title belongs to the *placement*, not to the component: `PageBlock`
    # carries one and `block.html` draws it in the card header. A component
    # drawing its own would put two inside one card, free to disagree — and
    # this one was declared and read by nothing.
    #
    # `page_size` and `sort` come from `TabularConfig`.
    #: CSS length, passed through to the widget. Empty lets it decide.
    height: str = ""
    #: A column whose value links to the row's detail page.
    row_link_field: str = ""
    #: What the table says when nothing matched. Blank uses the default.
    empty_text: str = ""

    # --- appearance ---------------------------------------------------------
    # Config rather than CSS, because density is a property of *this* screen:
    # a reference list wants room to read and an operational one wants rows on
    # screen, from the same DataSource. Each maps to one modifier class, so a
    # style pack renames them like anything else.

    #: Alternate row shading, for a wide table the eye has to track across.
    striped: bool = False
    #: Tighter rows. More on screen, at the cost of scanning comfort.
    compact: bool = False
    #: Vertical rules between columns.
    bordered: bool = False


@register_component("table_plinta", label="Table")
class TableComponent(Component):
    """Rows and columns, rendered on the server.

    No grid library. Sorting, paging and filtering are the server's, reached by
    ordinary links and the page's filter bar, so a viewer needs no JavaScript.
    A consumer wanting client-side sorting, column resizing or inline cell
    editing installs `table_tabulator`, or registers their own.

    The key names its implementation like every other — `table_plinta` beside
    `table_tabulator` — so core's component is no more privileged in the
    registry than it is in the code.
    """

    config_schema = TableConfig
    #: Edge to edge: a cell carries its own padding, and the card's would
    #: double it at the rim while leaving the middle unchanged.
    padding = Padding.NONE
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
        return self.ordered(rows, config), fields

    def ordered(self, rows, config: TableConfig):
        """``rows`` in the order the config asks for."""
        return ordered(rows, config.sort)

    def page(self, rows, config: TableConfig, number: int = 1) -> Page:
        """One page of ``rows``, and what a pager needs to draw itself."""
        return paged(rows, config.page_size, number)

    def requested_sort(self, config: TableConfig, context: dict) -> TableConfig:
        """The config, with a sort the viewer asked for replacing the block's.

        One column, because a heading is one click — the widget that fetches
        can send several, and `sort_asked` takes as many as it is given.
        """
        sort = sort_asked([context.get("sort") or ""], context.get("fields"))
        if not sort:
            return config
        return config.model_copy(update={"sort": sort[:1]})

    def navigation(self, config: TableConfig, page, context: dict) -> dict:
        """The links this table is navigated by, built from the current query.

        Built from the whole query string rather than from nothing, so sorting
        keeps the filters and paging keeps the sort. A link that dropped them
        would look like it worked and quietly widen the result.

        Returns nothing when the caller passed no query: an export has no URL
        to hang a sort link on.
        """
        query = context.get("query")
        if query is None:
            return {}

        prefix = context.get("param_prefix", "")
        sort_key, page_key = f"{prefix}sort", f"{prefix}page"
        current = {s.field: s.direction for s in config.sort}

        def with_params(**changes):
            """The current query with some parameters changed. None removes one."""
            params = dict(query.items()) if hasattr(query, "items") else dict(query)
            for key, value in changes.items():
                if value is None:
                    params.pop(key, None)
                else:
                    params[key] = value
            return "?" + urlencode(params)

        return {
            "sort_urls": {
                f.field_name: with_params(
                    **{
                        # Clicking a sorted column reverses it; clicking another
                        # starts ascending. Paging resets, since page four of a
                        # different order is a different four rows.
                        sort_key: f"-{f.field_name}"
                        if current.get(f.field_name) == "asc"
                        else f.field_name,
                        page_key: None,
                    }
                )
                for f in self.sortable(config, context)
            },
            "sorted_by": current,
            "page": page,
            "page_urls": {
                "previous": with_params(**{page_key: page.previous_page_number()})
                if page.has_previous()
                else "",
                "next": with_params(**{page_key: page.next_page_number()})
                if page.has_next()
                else "",
            },
        }

    def sortable(self, config: TableConfig, context: dict) -> list:
        """The columns a heading may link on. Every one it was given."""
        return context.get("fields") or []

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
        # The sort is honoured after the columns are known, because which
        # columns the viewer may see is what decides which may be sorted on —
        # and asking for them twice would be a query per block.
        config = self.requested_sort(config, {**context, "fields": fields})
        rows = self.ordered(rows, config)
        page = self.page(rows, config, context.get("page", 1))
        renderer = get_renderer(context.get("format", "html"))
        return renderer.render(
            page.object_list,
            fields,
            config.model_dump(),
            user,
            # Where a record of this DataSource opens, if anywhere. The page
            # supplies it — a table sits on a dashboard and the record is
            # shown elsewhere — so it travels rather than being derived.
            record_url=context.get("record_url", ""),
            **self.navigation(config, page, {**context, "fields": fields}),
        )

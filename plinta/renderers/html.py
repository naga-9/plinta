"""The HTML renderer: rows and columns as a table.

The one format core ships. Excel, PDF and email ship with `contrib.export`,
whose dependencies — `openpyxl`, `pandas`, `weasyprint` and its native
libraries — none of a screen needs.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.utils.html import escape, format_html, format_html_join
from django.utils.safestring import SafeString, mark_safe

from plinta.renderers.base import Renderer
from plinta.renderers.fields import render_field
from plinta.renderers.registry import register_renderer
from plinta.utils.styles import classes

#: Formats whose value is already markup and is emitted unescaped.
MARKUP_FORMATS = frozenset({"html"})

#: What a table with no rows says, when the block does not word it itself.
EMPTY_TEXT = "No records"

#: Drawn beside a sorted column.
ARROWS = {"asc": "↑", "desc": "↓"}


def value_of(row: Any, path: str) -> Any:
    """Follow a column path across a row.

    Traverses ``region__name``, and stops at the first missing or null step
    rather than raising: a null relation is an empty cell, not an error.

    A field with ``choices`` yields its **label**, through Django's own
    ``get_<field>_display``. A column showing `placed` where the model says
    "Placed" is showing the database's answer to a question the reader asked
    of the application.
    """
    parts = path.split("__")
    value = row
    for index, part in enumerate(parts):
        if value is None:
            return None
        if index == len(parts) - 1:
            display = getattr(value, f"get_{part}_display", None)
            if callable(display):
                return display()
        value = getattr(value, part, None)
    return value


def cell(row: Any, field: Any, user=None) -> SafeString:
    """One cell's content, as markup that is already safe to insert.

    A field renderer's output and an ``html`` column are markup by intent.
    Everything else is escaped here rather than by the caller, so there is no
    way to use this function and get the escaping wrong.
    """
    value = value_of(row, field.field_name)
    drawn = render_field(value, field, obj=row, user=user)
    if getattr(field, "renderer", "") or getattr(field, "format", "") in MARKUP_FORMATS:
        return mark_safe(drawn)  # noqa: S308 - the renderer or column is trusted
    return escape(drawn)


@register_renderer("html")
class HtmlRenderer(Renderer):
    """Rows as a table, with one cell per permitted column."""

    def render(
        self,
        rows: Iterable[Any],
        fields: Iterable[Any],
        config: dict[str, Any] | None = None,
        user=None,
        **context: Any,
    ) -> str:
        fields = list(fields)
        config = config or {}
        header = format_html_join(
            "", "<th>{}</th>", ((self.heading(f, context),) for f in fields)
        )
        body = format_html_join(
            "",
            "<tr>{}</tr>",
            (
                (
                    format_html_join(
                        "", "<td>{}</td>", ((cell(row, f, user),) for f in fields)
                    ),
                )
                for row in rows
            ),
        )
        if not body:
            body = self.empty_row(fields, config.get("empty_text") or EMPTY_TEXT)
        cls = classes()
        return format_html(
            '<div class="{}"><table class="{}">'
            "<thead><tr>{}</tr></thead><tbody>{}</tbody></table></div>{}",
            cls["table_wrap"],
            self.table_class(cls, config),
            header,
            body,
            self.pager(context.get("page"), context.get("page_urls") or {}),
        )

    def table_class(self, cls: dict[str, str], config: dict[str, Any]) -> str:
        """The table's classes: the base one, plus whatever the block asked for.

        A fixed order rather than the config's, so the attribute reads the same
        whichever way the flags were set — a diff of two blocks should show
        what differs, not how it was typed.
        """
        names = [cls["table"]]
        names += [
            cls[f"table_{flag}"]
            for flag in ("striped", "compact", "bordered")
            if config.get(flag)
        ]
        return " ".join(names)

    def heading(self, field: Any, context: dict[str, Any]) -> SafeString:
        """A column heading, as a sort link when the caller supplied one.

        Sorting is a link because the server does it: a differently ordered
        query is another request, and a link is what makes that work with no
        JavaScript and stay a URL someone can share.
        """
        url = (context.get("sort_urls") or {}).get(field.field_name)
        if not url:
            return escape(field.label)
        direction = (context.get("sorted_by") or {}).get(field.field_name)
        arrow = ARROWS.get(direction, "")
        cls = classes()
        return format_html(
            '<a class="{}{}" href="{}">{}{}</a>',
            cls["table_sort"],
            f" {cls['table_sort_active']}" if direction else "",
            url,
            field.label,
            format_html('<span aria-hidden="true"> {}</span>', arrow) if arrow else "",
        )

    def empty_row(self, fields: list[Any], text: str) -> SafeString:
        """What a table with no rows says.

        A table drawn with an empty body reads as broken; one that says so
        reads as a filter that matched nothing, which is what it usually is.
        """
        return format_html(
            '<tr class="{}"><td colspan="{}">{}</td></tr>',
            classes()["table_empty"],
            max(len(fields), 1),
            text,
        )

    def pager(self, page: Any, urls: dict[str, str]) -> SafeString:
        """Where in the rows this is, and how to reach the rest.

        Absent when everything fits on one page: a pager offering nowhere to
        go is furniture.

        A **list**, because a set of links is one — a screen reader announces
        how many there are and offers list navigation. Three of the four
        frameworks worth theming want the same shape, which is a consequence
        of that rather than the reason for it.
        """
        if page is None or page.paginator.num_pages <= 1:
            return mark_safe("")
        links = []
        if page.has_previous() and urls.get("previous"):
            links.append(("prev", urls["previous"], "Previous"))
        if page.has_next() and urls.get("next"):
            links.append(("next", urls["next"], "Next"))
        cls = classes()
        return format_html(
            '<nav class="{}" aria-label="Pages"><span class="{}">{} of {}</span>'
            '<ul class="{}">{}</ul></nav>',
            cls["pager"],
            cls["pager_status"],
            page.number,
            page.paginator.num_pages,
            cls["pager_list"],
            format_html_join(
                "",
                '<li class="{}"><a class="{}" rel="{}" href="{}">{}</a></li>',
                ((cls["pager_item"], cls["pager_link"], rel, url, label)
                 for rel, url, label in links),
            ),
        )

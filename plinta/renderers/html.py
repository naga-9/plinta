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

#: Formats whose value is already markup and is emitted unescaped.
MARKUP_FORMATS = frozenset({"html"})

#: What a table with no rows says, when the block does not word it itself.
EMPTY_TEXT = "No records"


def value_of(row: Any, path: str) -> Any:
    """Follow a column path across a row.

    Traverses ``region__name``, and stops at the first missing or null step
    rather than raising: a null relation is an empty cell, not an error.
    """
    value = row
    for part in path.split("__"):
        if value is None:
            return None
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
    ) -> str:
        fields = list(fields)
        header = format_html_join("", "<th>{}</th>", ((f.label,) for f in fields))
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
            body = self.empty_row(fields, (config or {}).get("empty_text") or EMPTY_TEXT)
        return format_html(
            "<table><thead><tr>{}</tr></thead><tbody>{}</tbody></table>", header, body
        )

    def empty_row(self, fields: list[Any], text: str) -> str:
        """What a table with no rows says.

        A table drawn with an empty body reads as broken; one that says so
        reads as a filter that matched nothing, which is what it usually is.
        """
        return format_html(
            '<tr class="pl-table__empty"><td colspan="{}">{}</td></tr>',
            max(len(fields), 1),
            text,
        )

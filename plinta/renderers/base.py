"""What every renderer is.

    render(rows, fields, config, user) -> output

Rows arrive already filtered by row policy, fields already filtered by field
permission. **A renderer never queries**: it cannot fetch what it was not
given, which is what makes this layer structurally incapable of widening
access.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from plinta.datasources.models import DataSourceField


class Renderer:
    """One output format.

    Subclasses set ``content_type`` when they produce something a browser
    should not treat as a page, and implement ``render``.
    """

    #: Sent when the output is returned over HTTP.
    content_type = "text/html; charset=utf-8"

    #: Appended when the output is offered as a file. Empty means it is not.
    extension = ""

    def render(
        self,
        rows: Iterable[Any],
        fields: Iterable[DataSourceField],
        config: dict[str, Any],
        user,
    ) -> Any:
        """Draw ``rows`` as this format.

        Args:
            rows: what the user may see, already narrowed.
            fields: the columns they may see, in display order.
            config: the component's resolved configuration.
            user: the viewer, for a field renderer that varies by them.
        """
        raise NotImplementedError

"""Arranging a page: which blocks are on it, and where each one sits.

**Core owns the write, not the dragging.** A placement's `column`, `row`,
`width` and `height` are four integers that map straight onto CSS grid (§9.3),
so a viewer renders the layout with no JavaScript. Changing them by dragging
is an enhancement, and `contrib.composer` supplies it by posting here — the
same endpoint the plain number form posts to. Uninstall it and you type the
numbers, which is a worse screen and an identical result.

That split is the reason the rule lives in one place: whatever moves a block,
`positions` is what decides whether it may.
"""
from __future__ import annotations

from typing import Any

from plinta.pages.models import Page, PageBlock

#: The grid is twelve columns (§9.3). A width beyond it is not a wider block,
#: it is a block that overflows its row, so it is clamped rather than refused —
#: a drag that ends slightly past the edge means the edge.
COLUMNS = 12

#: A row is a unit of the grid, not a pixel. Nothing needs a page taller than
#: this, and an unbounded row number from a bad client is a page that scrolls
#: for a thousand screens.
MAX_ROW = 200

#: A block one cell tall is a block nobody can read. Not a validation rule so
#: much as the smallest thing worth drawing.
MIN_SIZE = 1


class CompositionError(Exception):
    """A placement was moved somewhere it cannot go."""


def clamped(value: Any, low: int, high: int, fallback: int) -> int:
    """``value`` as an integer within ``low``..``high``.

    Anything unreadable becomes ``fallback`` rather than raising: these arrive
    from a drag, and one malformed number should move that block badly rather
    than lose the other eleven the same submission carried.
    """
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(low, min(high, number))


def placed(page: Page, user) -> list[PageBlock]:
    """The placements on ``page``, in the order they are drawn."""
    return list(
        page.placements.select_related("block", "block__data_source").order_by(
            "row", "column", "order", "pk"
        )
    )


def positions(page: Page, user, wanted: dict[int, dict[str, Any]]) -> list[PageBlock]:
    """Move placements on ``page``, returning the ones that changed.

    ``wanted`` is keyed by placement id, each value carrying any of ``column``,
    ``row``, ``width`` and ``height``. A key naming a placement on another page
    is **ignored rather than refused**: the id is a number in a POST body, and
    a client that guesses one should not thereby learn whether it exists.

    Nothing else about a placement is touched here — not the block it draws,
    not its title, not its tab. Moving and re-pointing are different acts.

    Raises:
        CompositionError: this viewer may not rearrange this page.
    """
    from plinta.permissions import can

    if not can(user, "change", page):
        raise CompositionError("you may not rearrange this page")

    mine = {placement.pk: placement for placement in page.placements.all()}
    moved = []
    for pk, values in wanted.items():
        placement = mine.get(int(pk))
        if placement is None:
            continue
        before = (placement.column, placement.row, placement.width, placement.height)
        placement.column = clamped(
            values.get("column", placement.column), 0, COLUMNS - 1, placement.column
        )
        placement.row = clamped(
            values.get("row", placement.row), 0, MAX_ROW, placement.row
        )
        placement.width = clamped(
            values.get("width", placement.width),
            MIN_SIZE,
            COLUMNS - placement.column,
            placement.width,
        )
        placement.height = clamped(
            values.get("height", placement.height), MIN_SIZE, MAX_ROW, placement.height
        )
        if (placement.column, placement.row, placement.width, placement.height) != before:
            moved.append(placement)

    if moved:
        PageBlock.objects.bulk_update(moved, ["column", "row", "width", "height"])
    return moved


def submitted_positions(post) -> dict[int, dict[str, Any]]:
    """Read ``position-<pk>-<field>`` out of a form submission.

    The plain number form's shape. `contrib.composer` posts JSON instead and
    reaches `positions` directly, so the two clients share the rule without
    sharing a wire format — a drag has no reason to speak in form fields.
    """
    wanted: dict[int, dict[str, Any]] = {}
    for key, value in post.items():
        parts = key.split("-")
        if len(parts) != 3 or parts[0] != "position":
            continue
        _, pk, field = parts
        if field not in {"column", "row", "width", "height"} or not pk.isdigit():
            continue
        wanted.setdefault(int(pk), {})[field] = value
    return wanted

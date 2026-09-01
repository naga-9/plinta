"""A column's value as the field holds it, rather than as a person reads it.

The counterpart of `renderers.html.cell`. A cell is formatted for reading —
`No`, `£8.75`, a chip — and none of those can be edited or sent back: an
editor seeded with `£8.75` returns `£8.75`, and one seeded with `No` returns
the word. So anything that writes needs the other half.

Here rather than in `blocks` because a component that draws a form needs it
and may not reach that far up, and because it is about a value and a field,
which is this layer's subject.
"""
from __future__ import annotations

import datetime
import decimal
from typing import Any


def raw(row: Any, name: str, kind: str) -> Any:
    """One value, ready to seed an editor or travel as JSON.

    JSON has no date and no Decimal, so both are sent in a form the browser
    can read back and the server can parse: a relation as the pk it is
    written by, a date as ISO-8601.
    """
    if kind == "relation":
        return getattr(row, f"{name}_id", None)
    if kind == "relations":
        # A manager, not a value: left alone it reaches JSON as one and the
        # whole payload fails to serialise. `.all()` rather than `values_list`,
        # which would go back to the database once per row and undo the
        # prefetch the column already asked for.
        return [related.pk for related in getattr(row, name).all()]
    value = getattr(row, name, None)
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    return value

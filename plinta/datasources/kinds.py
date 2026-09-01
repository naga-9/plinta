"""What a column holds, as against how it sorts.

`DataSourceField.sorter` answers "how do I compare this" and is a display
decision. This answers "what kind of value is this", read from the model, and
is what every behaviour that must match the data needs: which editor to draw,
which lookup to filter with, how to send the value at all.

Reading the sort hint instead is a mistake that has been made twice. Every
editable column got a text box, so a boolean cell reading `No` offered the
word back and was told it was not a boolean; and every non-text column filter
compiled to `icontains`, which is not a lookup a boolean or a relation has, so
the filter matched nothing and read as "no rows".

They agree for text and numbers and part company at booleans, dates and
relations — which is exactly where both failures were.
"""
from __future__ import annotations

from plinta.datasources.services import resolve_path

#: Django's field classes, by what they hold.
KINDS = {
    "AutoField": "number",
    "BigAutoField": "number",
    "BigIntegerField": "number",
    "BooleanField": "boolean",
    "DateField": "date",
    "DateTimeField": "datetime",
    "DecimalField": "number",
    "FloatField": "number",
    "IntegerField": "number",
    "PositiveIntegerField": "number",
    "PositiveSmallIntegerField": "number",
    "SmallIntegerField": "number",
    "TimeField": "time",
}

#: Kinds whose column joins more than one row, so a filter on one must be
#: made distinct: the join multiplies the rows and a page then shows a record
#: twice while the count says there are more than there are.
MULTIPLE = {"relations"}


def kind_of(model, path: str, fallback: str) -> str:
    """What the column at ``path`` holds.

    ``fallback`` is the sort hint, used where the path resolves to no model
    field — an annotation, a property, a reverse accessor. Those are readable
    and never editable, so a sort hint is all they need.
    """
    field = resolve_path(model, path)
    if field is None:
        return fallback
    if getattr(field, "many_to_one", False) or getattr(field, "one_to_one", False):
        return "relation"
    if getattr(field, "many_to_many", False):
        return "relations"
    return KINDS.get(type(field).__name__, "string")



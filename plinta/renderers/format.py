"""How a value looks, in every format.

HTML, a spreadsheet and an email all call these helpers, so a value looks the
same in each. What it looks like is declared on the ``DataSourceField``:
``decimals``, ``thousands_separator``, ``prefix``, ``suffix`` and ``format``.
"""
from __future__ import annotations

import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.utils import formats, timezone

if TYPE_CHECKING:  # a model import at module scope would break §20.1
    from plinta.datasources.models import DataSourceField

#: What a column shows when it has no value.
EMPTY = ""


def wants_number(field: DataSourceField | None) -> bool:
    """Whether this column wants a non-numeric value formatted as a number.

    True when it declares ``decimals`` or ``thousands_separator``, which is
    what makes a numeric string from an annotation render like a number.
    """
    if field is None:
        return False
    return (
        getattr(field, "decimals", None) is not None
        or bool(getattr(field, "thousands_separator", False))
    )


def decimals_for(field: DataSourceField | None) -> int | None:
    """How many decimal places this column asks for, or None for the value's own.

    None leaves the number alone: 1234.5 renders as 1234.5. Zero is an
    instruction to round to an integer.
    """
    return getattr(field, "decimals", None) if field is not None else None


def format_value(value: Any, field: DataSourceField | None = None) -> str:
    """``value`` as text, according to ``field``'s declared format.

    ``field`` may be None — a value with no column behind it, such as a
    placeholder — in which case the type alone decides.
    """
    if value is None:
        return EMPTY

    fmt = (getattr(field, "format", "") or "") if field is not None else ""

    if isinstance(value, (list, tuple)):
        # A collection column: its members, in the order the query gave them.
        # `str(row)` for each, the same label a picker offers.
        drawn = ", ".join(str(item) for item in value)
        return affix(drawn, field) if drawn else EMPTY
    if isinstance(value, bool):
        return affix(format_boolean(value), field)
    if isinstance(value, datetime.datetime):
        text = format_date(value) if fmt == "date" else format_datetime(value)
        return affix(text, field)
    if isinstance(value, datetime.date):
        return affix(format_date(value), field)
    if isinstance(value, datetime.time):
        return affix(formats.time_format(value), field)
    if wants_number(field) or isinstance(value, (int, float, Decimal)):
        text = format_number(value, field)
    else:
        text = str(value)
    return affix(text, field) if text else EMPTY


def format_boolean(value: bool) -> str:
    """A boolean as words, so a spreadsheet cell reads like the table did."""
    return "Yes" if value else "No"


def format_date(value: datetime.date) -> str:
    """Through Django's date machinery, so the active locale decides."""
    return formats.date_format(value, "DATE_FORMAT")


def format_datetime(value: datetime.datetime) -> str:
    """Localised to the active timezone, so a row does not show UTC."""
    if settings.USE_TZ and timezone.is_aware(value):
        value = timezone.localtime(value)
    return formats.date_format(value, "DATETIME_FORMAT")


def format_number(value: Any, field: DataSourceField | None = None) -> str:
    """The bare number, at the column's precision and grouping.

    The value is rendered as it is stored — a column holding 15 renders 15,
    never 1500. Scaling belongs in an annotation, where the arithmetic is
    visible. Anything drawn around the number is ``affix``'s.

    A value that is not a number is returned unchanged, since configuration
    can point a numeric column at a text field.
    """
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return str(value)

    places = decimals_for(field)
    if places is not None:
        # number_format truncates to decimal_pos, so round first: 1.999 at
        # two places is 2.00. quantize takes an exemplar whose exponent is the
        # target — Decimal(1).scaleb(-2) is Decimal("0.01") — and raises past
        # the context's significant digits, where the value is shown unrounded.
        try:
            number = number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
        except InvalidOperation:
            places = None
    return formats.number_format(
        number,
        decimal_pos=places,
        force_grouping=bool(getattr(field, "thousands_separator", False)),
    )


def affix(text: str, field: DataSourceField | None) -> str:
    """Put the column's prefix and suffix around a formatted value.

    Exactly what the column declared, in that order. Nothing is added and
    nothing is rearranged around a minus sign; a column needing an accounting
    style such as (5.00) registers a field renderer (§7.8).
    """
    prefix = (getattr(field, "prefix", "") or "") if field is not None else ""
    suffix = (getattr(field, "suffix", "") or "") if field is not None else ""
    return f"{prefix}{text}{suffix}"

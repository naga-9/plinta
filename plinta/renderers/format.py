"""How a value looks, in every format.

A date renders identically in HTML, in a spreadsheet and in an email because
all three call these helpers. Precision and grouping are declared once on the
``DataSourceField`` (§6.8) and honoured everywhere, rather than hardcoded per
renderer as they were in v1.
"""
from __future__ import annotations

import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.utils import formats, timezone

if TYPE_CHECKING:  # a model import at module scope would break §20.1
    from plinta.datasources.models import DataSourceField

#: What a column shows when it has no value. Not "None", not "0".
EMPTY = ""

#: Decimal places when the column does not say. v1's hardcoded values, kept —
#: what §6.8 added is the override, not new defaults.
DEFAULT_DECIMALS = {"currency": 2, "percent": 1, "number": 0}

#: Formats whose value is a number and is rendered as one.
NUMERIC_FORMATS = frozenset(DEFAULT_DECIMALS)


def decimals_for(field: DataSourceField | None) -> int | None:
    """How many decimal places this column asks for, or None to leave it alone."""
    if field is None:
        return None
    declared = getattr(field, "decimals", None)
    if declared is not None:
        return declared
    return DEFAULT_DECIMALS.get(getattr(field, "format", "") or "")


def format_value(value: Any, field: DataSourceField | None = None) -> str:
    """``value`` as text, according to ``field``'s declared format.

    ``field`` may be None — a value with no column behind it, such as a
    placeholder — in which case the type alone decides.
    """
    if value is None:
        return EMPTY

    fmt = (getattr(field, "format", "") or "") if field is not None else ""

    if isinstance(value, bool):
        return affix(format_boolean(value), field, fmt)
    if isinstance(value, datetime.datetime):
        return affix(format_datetime(value), field, fmt)
    if isinstance(value, datetime.date):
        return affix(format_date(value), field, fmt)
    if isinstance(value, datetime.time):
        return affix(formats.time_format(value), field, fmt)
    if fmt in NUMERIC_FORMATS or isinstance(value, (int, float, Decimal)):
        text = format_number(value, field)
    else:
        text = str(value)
    return affix(text, field, fmt) if text else EMPTY


def format_boolean(value: bool) -> str:
    """A checkbox column reads as words, in every format.

    Django's own ``BooleanField`` renders "True"/"False" through ``str``; a
    spreadsheet cell and an email both want the same words a table shows.
    """
    return "Yes" if value else "No"


def format_date(value: datetime.date) -> str:
    """Through Django's ``DATE_FORMAT``, so the consumer's settings win."""
    return formats.date_format(value, "DATE_FORMAT")


def format_datetime(value: datetime.datetime) -> str:
    """Localised to the active timezone first, or every row shows UTC."""
    if settings.USE_TZ and timezone.is_aware(value):
        value = timezone.localtime(value)
    return formats.date_format(value, "DATETIME_FORMAT")


def format_number(value: Any, field: DataSourceField | None = None) -> str:
    """A number with the column's precision, grouping, symbol and sign.

    The bare number. Whatever is drawn around it — a symbol, a unit, a sign —
    is ``affix``'s.

    ``percent`` treats the **stored value as the percentage**: 15 renders as
    "15.0%". Multiplying by a hundred here would make a renderer change the
    meaning of the data, and a column storing a 0–1 fraction is the rarer case
    — it declares an annotation that multiplies, where the arithmetic is
    visible.
    """
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return str(value)

    places = decimals_for(field)
    if places is not None:
        # Django's number_format *truncates* to decimal_pos, so 1.999 at two
        # places would show as 1.99. Money must round.
        number = number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    text = formats.number_format(
        number,
        decimal_pos=places,
        force_grouping=bool(getattr(field, "thousands_separator", False)),
    )

    return text


def affix(text: str, field: DataSourceField | None, fmt: str) -> str:
    """Put the column's prefix and suffix around a formatted number.

    A declared affix **replaces** what the format would have drawn, so a
    ``percent`` column with ``suffix='%'`` shows one sign rather than two.
    ``percent`` is the only format that draws anything of its own: a sign is
    what the format *means*, where a currency symbol is a fact about the data
    that core has no way to know.
    """
    prefix = (getattr(field, "prefix", "") or "") if field is not None else ""
    suffix = (getattr(field, "suffix", "") or "") if field is not None else ""
    if not prefix and not suffix and fmt == "percent":
        suffix = "%"
    if prefix and text.startswith("-"):
        # -$5.00, which is what every spreadsheet writes, not $-5.00.
        return f"-{prefix}{text[1:]}{suffix}"
    return f"{prefix}{text}{suffix}"

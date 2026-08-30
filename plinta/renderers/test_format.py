"""One value, one appearance — whichever format is asking."""
import datetime
from decimal import Decimal

import pytest
from django.test import override_settings
from django.utils import translation

from plinta.renderers.format import (
    decimals_for,
    format_boolean,
    format_date,
    format_datetime,
    format_number,
    format_value,
)


class Field:
    """The parts of a DataSourceField a formatter reads."""

    def __init__(self, format="", decimals=None, thousands_separator=False):
        self.format = format
        self.decimals = decimals
        self.thousands_separator = thousands_separator


# --- nothing ---------------------------------------------------------------


def test_none_is_an_empty_cell():
    """Not "None", which is what str() would give and what v1 showed."""
    assert format_value(None) == ""


def test_none_is_empty_whatever_the_format_says():
    assert format_value(None, Field(format="currency")) == ""


def test_an_empty_string_stays_empty():
    assert format_value("") == ""


def test_zero_is_not_empty():
    assert format_value(0, Field(format="number")) == "0"


# --- booleans --------------------------------------------------------------


def test_a_boolean_reads_as_words():
    assert (format_boolean(True), format_boolean(False)) == ("Yes", "No")


def test_a_boolean_is_not_treated_as_a_number():
    """bool is a subclass of int, so the order of the checks matters."""
    assert format_value(True, Field(format="number")) == "Yes"


# --- dates -----------------------------------------------------------------


def test_a_date_goes_through_django_format():
    assert format_date(datetime.date(2026, 1, 9)) == "Jan. 9, 2026"


def test_the_active_locale_decides():
    """Django 6 localises unconditionally, so the locale's format wins over the
    DATE_FORMAT setting. plinta does not second-guess that choice."""
    with translation.override("de"):
        assert format_date(datetime.date(2026, 1, 9)) == "9. Januar 2026"


def test_a_naive_datetime_is_left_alone():
    value = datetime.datetime(2026, 1, 9, 14, 30)
    assert "2:30" in format_datetime(value)


@override_settings(USE_TZ=True, TIME_ZONE="America/Toronto")
def test_an_aware_datetime_is_localised():
    """Without this every row shows UTC and nobody notices until a deadline."""
    value = datetime.datetime(2026, 1, 9, 19, 30, tzinfo=datetime.UTC)
    assert "2:30 p.m." in format_datetime(value)


def test_a_time_formats():
    assert "2:30" in format_value(datetime.time(14, 30))


# --- numbers ---------------------------------------------------------------


def test_a_plain_number_keeps_its_places():
    assert format_number(Decimal("1234.5")) == "1234.5"


def test_number_defaults_to_no_decimals():
    assert format_value(Decimal("1234"), Field(format="number")) == "1234"


def test_a_column_may_ask_for_four_decimals():
    """The ceiling v1 had: precision was hardcoded per format."""
    assert format_value(Decimal("1.23456"), Field(format="number", decimals=4)) == "1.2346"


def test_zero_decimals_is_not_the_same_as_unset():
    assert decimals_for(Field(format="number", decimals=0)) == 0


def test_thousands_grouping_is_opt_in():
    plain = Field(format="number")
    grouped = Field(format="number", thousands_separator=True)
    assert format_value(1234567, plain) == "1234567"
    assert format_value(1234567, grouped) == "1,234,567"


def test_it_rounds_rather_than_truncates():
    """Django's number_format truncates; $1.99 for 1.999 is a wrong number."""
    assert format_value(Decimal("1.999"), Field(format="currency")) == "$2.00"


def test_a_half_rounds_up():
    assert format_value(Decimal("15.25"), Field(format="percent")) == "15.3%"


def test_a_non_number_in_a_number_column_is_not_a_crash():
    """Configuration can point a numeric format at a text column."""
    assert format_value("n/a", Field(format="number")) == "n/a"


# --- currency --------------------------------------------------------------


def test_currency_defaults_to_two_places_and_a_symbol():
    assert format_value(Decimal("1234.5"), Field(format="currency")) == "$1234.50"


def test_currency_keeps_the_sign_outside_the_symbol():
    """-$5.00, not $-5.00."""
    assert format_value(Decimal("-5"), Field(format="currency")) == "-$5.00"


@override_settings(PLINTA_CURRENCY_SYMBOL="€")
def test_the_symbol_is_a_setting():
    assert format_value(Decimal("5"), Field(format="currency")) == "€5.00"


def test_a_currency_column_may_override_its_precision():
    assert format_value(Decimal("1.2345"), Field(format="currency", decimals=4)) == "$1.2345"


# --- percent ---------------------------------------------------------------


def test_the_stored_value_is_the_percentage():
    """15 renders as 15.0%. Multiplying here would change the data's meaning."""
    assert format_value(15, Field(format="percent")) == "15.0%"


def test_percent_defaults_to_one_place():
    assert format_value(Decimal("15.25"), Field(format="percent")) == "15.3%"


# --- everything else -------------------------------------------------------


def test_text_passes_through():
    assert format_value("Dune", Field()) == "Dune"


def test_an_object_renders_as_its_str():
    class Region:
        def __str__(self):
            return "North"

    assert format_value(Region()) == "North"


def test_a_value_with_no_column_behind_it_is_still_formatted():
    """A placeholder has no DataSourceField; the type alone decides."""
    assert format_value(datetime.date(2026, 1, 9)) == "Jan. 9, 2026"

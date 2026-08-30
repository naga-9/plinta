"""One value, one appearance — whichever format is asking."""
import datetime
from decimal import Decimal

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

    def __init__(
        self,
        format="",
        decimals=None,
        thousands_separator=False,
        prefix="",
        suffix="",
    ):
        self.format = format
        self.decimals = decimals
        self.thousands_separator = thousands_separator
        self.prefix = prefix
        self.suffix = suffix


# --- nothing ---------------------------------------------------------------


def test_none_is_an_empty_cell():
    """Not "None", which is what str() would give and what v1 showed."""
    assert format_value(None) == ""


def test_none_is_empty_whatever_the_format_says():
    assert format_value(None, Field()) == ""


def test_an_empty_string_stays_empty():
    assert format_value("") == ""


def test_zero_is_not_empty():
    assert format_value(0, Field()) == "0"


# --- booleans --------------------------------------------------------------


def test_a_boolean_reads_as_words():
    assert (format_boolean(True), format_boolean(False)) == ("Yes", "No")


def test_a_boolean_is_not_treated_as_a_number():
    """bool is a subclass of int, so the order of the checks matters."""
    assert format_value(True, Field()) == "Yes"


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


def test_an_unset_column_keeps_the_values_own_precision():
    """Not zero places — that would round 5.49 to 5 and look entirely correct."""
    assert format_value(Decimal("1234.5"), Field()) == "1234.5"
    assert format_value(Decimal("1234"), Field()) == "1234"


def test_a_column_may_ask_for_four_decimals():
    """The ceiling v1 had: precision was hardcoded per format."""
    assert format_value(Decimal("1.23456"), Field(decimals=4)) == "1.2346"


def test_zero_decimals_is_not_the_same_as_unset():
    assert decimals_for(Field(decimals=0)) == 0


def test_thousands_grouping_is_opt_in():
    plain = Field()
    grouped = Field(thousands_separator=True)
    assert format_value(1234567, plain) == "1234567"
    assert format_value(1234567, grouped) == "1,234,567"


def test_it_rounds_rather_than_truncates():
    """Django's number_format truncates; 1.99 for 1.999 is a wrong number."""
    assert format_value(Decimal("1.999"), Field(decimals=2)) == "2.00"


def test_a_half_rounds_up():
    assert format_value(Decimal("15.25"), Field(decimals=1)) == "15.3"


def test_a_number_too_large_to_round_is_still_shown():
    """quantize raises past the context's 28 significant digits. A total that
    big is still a number worth showing, not a 500."""
    field = Field(decimals=4)
    assert format_value(Decimal("1e30"), field).startswith("1")


def test_text_in_a_numeric_column_is_not_a_crash():
    """Configuration can point a numeric format at a text column."""
    assert format_value("n/a", Field()) == "n/a"


# --- currency --------------------------------------------------------------


def test_nothing_imposes_a_precision():
    """The column says, or the value does. There is no format that decides."""
    assert format_value(Decimal("1234.5"), Field()) == "1234.5"


def test_a_column_draws_its_own_symbol():
    field = Field(prefix="$", decimals=2)
    assert format_value(Decimal("5"), field) == "$5.00"


def test_two_currencies_on_one_screen():
    """Which a setting could never express."""
    usd = Field(prefix="$", decimals=2)
    eur = Field(prefix="€", decimals=2)
    assert format_value(Decimal("5"), usd) == "$5.00"
    assert format_value(Decimal("5"), eur) == "€5.00"


def test_core_draws_no_symbol():
    """Which symbol a column wants is a fact about the data. Core formats the
    number and draws whatever the column declared — nothing more."""
    assert format_value(Decimal("5"), Field()) == "5"


def test_a_column_declaring_nothing_is_just_a_number():
    assert format_value(Decimal("5"), Field()) == "5"


def test_nothing_is_rearranged_around_a_minus():
    """Accounting writes (5.00), some styles -$5.00, others $-5.00. Any
    convention core picked would be wrong for someone; a column wanting one
    registers a field renderer (§7.8)."""
    field = Field(prefix="$", decimals=2)
    assert format_value(Decimal("-5"), field) == "$-5.00"


def test_a_negative_with_only_a_suffix_is_untouched():
    assert format_value(Decimal("-5"), Field(suffix="kg")) == "-5kg"


def test_a_money_column_asks_for_its_own_precision():
    """Four places on a price column — the ceiling v1 had."""
    field = Field(prefix="$", decimals=4)
    assert format_value(Decimal("1.2345"), field) == "$1.2345"


# --- affixes ---------------------------------------------------------------


def test_a_suffix_is_drawn_after():
    assert format_value(Decimal("1.5"), Field(decimals=1, suffix="kg")) == "1.5kg"


def test_a_prefix_and_a_suffix_together():
    field = Field(decimals=0, prefix="~", suffix=" ms")
    assert format_value(180, field) == "~180 ms"


def test_an_affix_needs_no_format():
    assert format_value(5, Field(suffix="°C")) == "5°C"


def test_a_percentage_is_a_suffix_and_nothing_more():
    """There is no percent format; the sign is drawn because it was declared."""
    assert format_value(15, Field()) == "15"
    assert format_value(15, Field(suffix="%")) == "15%"


def test_a_symbol_may_go_after():
    field = Field(suffix=" kr", decimals=2)
    assert format_value(Decimal("5"), field) == "5.00 kr"


def test_an_empty_column_draws_nothing_extra():
    assert format_value(5, Field()) == "5"


def test_an_affix_decorates_any_value_not_only_a_number():
    """A suffix on a date column drawing nothing would be a silent no-op."""
    field = Field(suffix=" (est.)")
    assert format_value(datetime.date(2026, 1, 9), field) == "Jan. 9, 2026 (est.)"


def test_text_takes_an_affix_too():
    assert format_value("Dune", Field(prefix="«", suffix="»")) == "«Dune»"


def test_an_empty_cell_gets_no_affix():
    """Otherwise a blank currency column renders as a lone symbol."""
    assert format_value(None, Field(prefix="$")) == ""
    assert format_value("", Field(prefix="$")) == ""


# --- percent ---------------------------------------------------------------


def test_the_stored_value_is_the_percentage():
    """15 renders as 15, not 1500. Multiplying here would change the meaning
    of the data — a fraction declares an annotation, where it is visible."""
    assert format_value(15, Field(suffix="%")) == "15%"


# --- the formats that survive ----------------------------------------------


def test_a_datetime_column_may_show_the_day_only():
    """The one thing no knob can say, which is why the choice still exists."""
    value = datetime.datetime(2026, 1, 9, 14, 30)
    assert format_value(value, Field(format="date")) == "Jan. 9, 2026"


def test_a_datetime_shows_its_time_by_default():
    value = datetime.datetime(2026, 1, 9, 14, 30)
    assert "2:30" in format_value(value, Field())


def test_the_knobs_decide_numeric_treatment_not_a_format():
    """A string from an annotation is formatted as a number because the column
    asked for decimals, not because it declared format='number'."""
    assert format_value("1234.5", Field(decimals=2)) == "1234.50"
    assert format_value("1234.5", Field()) == "1234.5"


def test_grouping_alone_is_enough_to_mean_numeric():
    assert format_value("1234567", Field(thousands_separator=True)) == "1,234,567"


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

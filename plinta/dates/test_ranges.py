"""Range resolution against a fixed today, and the registry contrib extends."""
from datetime import date

import pytest
from django.db.models import Q

from plinta.dates.ranges import (
    RangeError,
    add_months,
    month_end,
    month_start,
    options,
    resolve_q,
)

# A month with 31 days, mid-year, so month arithmetic is exercised without
# leap-year or year-boundary noise unless a test asks for it.
TODAY = date(2026, 8, 15)


def bounds(q):
    """The lookup -> value pairs of a leaf Q."""
    return dict(q.children)


def test_past_is_strictly_before_today():
    assert bounds(resolve_q("due", "past", TODAY)) == {"due__lt": TODAY}


def test_current_month_spans_the_whole_month():
    assert bounds(resolve_q("due", "current_month", TODAY)) == {
        "due__gte": date(2026, 8, 1),
        "due__lte": date(2026, 8, 31),
    }


def test_next_month_starts_after_the_current_one():
    """'Next Month' excludes today's month — that is its own option."""
    assert bounds(resolve_q("due", "next_month", TODAY)) == {
        "due__gte": date(2026, 9, 1),
        "due__lte": date(2026, 9, 30),
    }


def test_next_3_months_is_the_three_months_after_this_one():
    assert bounds(resolve_q("due", "next_3_months", TODAY)) == {
        "due__gte": date(2026, 9, 1),
        "due__lte": date(2026, 11, 30),
    }


def test_next_12_months_crosses_the_year_boundary():
    assert bounds(resolve_q("due", "next_12_months", date(2026, 12, 5))) == {
        "due__gte": date(2027, 1, 1),
        "due__lte": date(2027, 12, 31),
    }


def test_february_in_a_leap_year():
    assert month_end(date(2028, 2, 3)) == date(2028, 2, 29)


def test_several_names_are_ored():
    q = resolve_q("due", ["past", "current_month"], TODAY)
    assert q.connector == Q.OR
    assert len(q.children) == 2


def test_an_unknown_name_is_ignored():
    assert bounds(resolve_q("due", ["past", "nonsense"], TODAY)) == {"due__lt": TODAY}


def test_nothing_matching_means_no_filter_not_no_rows():
    assert resolve_q("due", ["nonsense"], TODAY) is None
    assert resolve_q("due", [], TODAY) is None


def test_the_field_name_is_used_verbatim():
    """So a traversed path filters on the related model's column."""
    assert bounds(resolve_q("order__due", "past", TODAY)) == {"order__due__lt": TODAY}


def test_today_defaults_to_the_real_today():
    assert bounds(resolve_q("due", "past"))["due__lt"] == date.today()


def test_a_contrib_package_registers_its_own(range_registry):
    range_registry.register_range(
        "current_fiscal_year",
        "Current Fiscal Year",
        lambda field, today: Q(**{f"{field}__year": today.year}),
    )
    assert bounds(resolve_q("due", "current_fiscal_year", TODAY)) == {"due__year": 2026}


@pytest.mark.parametrize("name", ["Current Month", "current month", "1st", "with-dash", ""])
def test_an_unusable_range_name_is_refused(range_registry, name):
    """A range name is stored in config, so it follows the same rule as a token."""
    with pytest.raises(RangeError):
        range_registry.register_range(name, "X", lambda field, today: Q())


def test_a_duplicate_name_is_refused(range_registry):
    range_registry.register_range("x", "X", lambda field, today: Q())
    with pytest.raises(RangeError, match="already registered"):
        range_registry.register_range("x", "X again", lambda field, today: Q())


def test_options_offers_core_seven_in_order():
    assert [r.name for r in options()] == [
        "past",
        "current_month",
        "next_month",
        "next_2_months",
        "next_3_months",
        "next_6_months",
        "next_12_months",
    ]


def test_options_carry_a_label_for_the_filter_ui():
    assert {r.label for r in options()} >= {"Past", "Current Month", "Next 12 Months"}


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (date(2026, 1, 31), 1, date(2026, 2, 1)),
        (date(2026, 12, 1), 1, date(2027, 1, 1)),
        (date(2026, 3, 15), 12, date(2027, 3, 1)),
        (date(2026, 8, 15), 0, date(2026, 8, 1)),
    ],
)
def test_add_months_returns_a_month_start(start, months, expected):
    assert add_months(start, months) == expected


def test_month_start():
    assert month_start(TODAY) == date(2026, 8, 1)

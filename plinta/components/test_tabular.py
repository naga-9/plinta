"""Ordering, paging and column filtering, on their own.

These are the shared half of every row-drawing component, so they are tested
without one: a failure here is a failure of the table, of Tabulator, and of
whatever is registered next.
"""
import pytest
from django.contrib.contenttypes.models import ContentType

from plinta.components.tabular import (
    Sort,
    filtered,
    ordered,
    paged,
    sort_asked,
)
from plinta.datasources.models import DataSource, DataSourceField, Sorter
from tests.testapp.models import Book


@pytest.fixture
def fields(db):
    source = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    DataSourceField.objects.create(
        data_source=source, field_name="title", label="Title", filterable=True
    )
    DataSourceField.objects.create(
        data_source=source,
        field_name="id",
        label="Number",
        sorter=Sorter.NUMBER,
        filterable=True,
    )
    # Visible, and not open to filtering. The two are separate decisions.
    DataSourceField.objects.create(
        data_source=source, field_name="in_print", label="In print"
    )
    return list(source.fields.all())


@pytest.fixture
def books(db):
    Book.objects.create(title="Ariel", in_print=False)
    Book.objects.create(title="Crow", in_print=True)
    Book.objects.create(title="Birthday Letters", in_print=True)
    return Book.objects.all()


# --- ordering ---------------------------------------------------------------


def test_ordered_applies_the_sort(books):
    rows = ordered(books, [Sort(field="title", direction="desc")])
    assert [b.title for b in rows] == ["Crow", "Birthday Letters", "Ariel"]


def test_ordered_is_never_unordered(books):
    """An unordered queryset can put one row on two pages and another on none."""
    assert ordered(books, []).query.order_by


def test_ordered_keeps_an_existing_order(books):
    assert ordered(books.order_by("title"), []).query.order_by == ("title",)


# --- paging -----------------------------------------------------------------


def test_paged_returns_that_page(books):
    page = paged(ordered(books, [Sort(field="title")]), 2, 2)
    assert [b.title for b in page.object_list] == ["Crow"]
    assert page.paginator.num_pages == 2


def test_paged_survives_a_number_nobody_can_reach(books):
    """A page number in a link someone typed lands somewhere, never raises."""
    assert paged(ordered(books, []), 2, "nonesuch").number == 1
    assert paged(ordered(books, []), 2, 99).number == 2


# --- the sort a viewer asks for ---------------------------------------------


def test_sort_asked_reads_the_prefix(fields):
    assert sort_asked(["-title"], fields) == [Sort(field="title", direction="desc")]


def test_sort_asked_takes_several(fields):
    assert [s.field for s in sort_asked(["in_print", "-title"], fields)] == [
        "in_print",
        "title",
    ]


def test_sort_asked_drops_a_column_the_viewer_was_not_given(fields):
    """Ordering on a hidden column leaks its values through the row order."""
    assert sort_asked(["isbn"], fields) == []


def test_sort_asked_ignores_blanks(fields):
    assert sort_asked(["", "  "], fields) == []


# --- the filters a viewer types ---------------------------------------------


def test_filtered_narrows_on_a_filterable_column(books, fields):
    rows = filtered(books, {"title": "row"}, fields)
    assert {b.title for b in rows} == {"Crow"}


def test_filtered_is_case_insensitive_and_partial(books, fields):
    assert filtered(books, {"title": "ARIE"}, fields).count() == 1


def test_filtered_ands_across_columns(books, fields):
    crow = Book.objects.get(title="Crow")
    assert filtered(books, {"title": "r", "id": str(crow.pk)}, fields).count() == 1


def test_filtered_ignores_a_column_the_author_did_not_open(books, fields):
    """`in_print` is visible and not filterable, so typing at it does nothing."""
    assert filtered(books, {"in_print": "true"}, fields).count() == 3


def test_filtered_ignores_a_column_the_viewer_was_not_given(books, fields):
    """The gate that matters: a path never exposed cannot be reached by
    typing it into a query string. v1 checked only the *head* of the
    traversal, so `owner__password__startswith` was a search box."""
    assert filtered(books, {"region__name": "North"}, fields).count() == 3
    assert filtered(books, {"owner__password": "x"}, fields).count() == 3


def test_filtered_ignores_an_empty_value(books, fields):
    assert filtered(books, {"title": ""}, fields).count() == 3


def test_a_number_column_matches_exactly(books, fields):
    """`icontains` on a number column would raise, and `1` would find `10`."""
    crow = Book.objects.get(title="Crow")
    rows = filtered(books, {"id": str(crow.pk)}, fields)
    assert [b.title for b in rows] == ["Crow"]


def test_a_value_the_column_cannot_hold_finds_nothing(books, fields):
    """It came from a text box, so a bad value is normal, not a 500.

    Both timings are covered by the one guard: an integer column rejects the
    value while the query is being *built*, and a date column not until it is
    read — so the try wraps the call and the evaluation together.
    """
    assert filtered(books, {"id": "cheap"}, fields).count() == 0

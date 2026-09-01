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
from tests.testapp.models import Book, Region


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


# --- filtering a column that is not text ------------------------------------
#
# The lookup used to come from `sorter`, so every one of these compiled to
# `icontains` — not a lookup a boolean or a relation has. The filter raised,
# was caught, and matched nothing: filtering by region emptied the table and
# read as "there is no data".


@pytest.fixture
def typed(db):
    """Columns of each kind, all filterable."""
    source = DataSource.objects.create(
        name="typed",
        label="Typed",
        content_type=ContentType.objects.get_for_model(Book),
    )
    for name in ("title", "in_print", "region", "watchers"):
        DataSourceField.objects.create(
            data_source=source, field_name=name, label=name, filterable=True
        )
    return list(source.fields.all())


@pytest.fixture
def catalogue(db):
    from django.contrib.auth.models import User

    north = Region.objects.create(name="North")
    south = Region.objects.create(name="South")
    bob = User.objects.create_user(username="bob", password="x")  # noqa: S106
    cal = User.objects.create_user(username="cal", password="x")  # noqa: S106
    first = Book.objects.create(title="Ariel", in_print=True, region=north)
    second = Book.objects.create(title="Crow", in_print=False, region=south)
    first.watchers.set([bob, cal])
    second.watchers.set([bob])
    return {"north": north, "bob": bob, "first": first, "second": second}


def test_a_boolean_column_filters(typed, catalogue):
    rows = filtered(Book.objects.all(), {"in_print": "true"}, typed)
    assert [b.title for b in rows] == ["Ariel"]


def test_a_boolean_takes_the_spelling_our_own_controls_send(typed, catalogue):
    """Django's `to_python` refuses a lowercase `true`, which is ours."""
    for text in ("true", "True", "1", "yes"):
        assert filtered(Book.objects.all(), {"in_print": text}, typed).count() == 1
    for text in ("false", "False", "0", "no"):
        assert filtered(Book.objects.all(), {"in_print": text}, typed).count() == 1


def test_a_relation_filters_by_pk(typed, catalogue):
    rows = filtered(Book.objects.all(), {"region": catalogue["north"].pk}, typed)
    assert [b.title for b in rows] == ["Ariel"]


def test_a_many_to_many_filters_by_pk(typed, catalogue):
    rows = filtered(Book.objects.all(), {"watchers": catalogue["bob"].pk}, typed)
    assert sorted(b.title for b in rows) == ["Ariel", "Crow"]


def test_a_many_to_many_filter_does_not_double_a_row(typed, catalogue):
    """The join multiplies rows: without `distinct` a record with two
    watchers appears twice on the page and the count overstates the total."""
    both = list(catalogue["first"].watchers.values_list("pk", flat=True))
    rows = filtered(
        Book.objects.all(), {"watchers": both[0]}, typed
    ) | filtered(Book.objects.all(), {"watchers": both[1]}, typed)
    assert filtered(
        Book.objects.all(), {"watchers": both[0]}, typed
    ).filter(title="Ariel").count() == 1
    assert rows.distinct().filter(title="Ariel").count() == 1


def test_a_text_column_still_matches_partially(typed, catalogue):
    assert filtered(Book.objects.all(), {"title": "rie"}, typed).count() == 1

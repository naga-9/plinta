"""Which joins a column set implies, and that they remove the N+1."""
import pytest
from django.contrib.auth.models import User

from plinta.datasources.prefetch import apply, derive
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db


# --- derivation ------------------------------------------------------------


def test_a_plain_column_needs_nothing():
    assert derive(Book, ["title"]) == (set(), set())


def test_a_traversed_path_joins_the_relation():
    assert derive(Book, ["region__name"]) == ({"region"}, set())


def test_a_relation_named_directly_still_joins():
    """Rendering it reads the related object, which is a query per row."""
    assert derive(Book, ["region"]) == ({"region"}, set())


def test_a_many_to_many_prefetches():
    assert derive(Book, ["watchers"]) == (set(), {"watchers"})


def test_a_traversed_many_to_many_prefetches_the_accessor():
    assert derive(Book, ["watchers__username"]) == (set(), {"watchers"})


def test_a_reverse_accessor_prefetches():
    assert derive(Region, ["book"]) == (set(), {"book"})


def test_a_path_that_does_not_resolve_is_skipped():
    """A property or an annotation is a legitimate column and joins nothing."""
    assert derive(Book, ["nonsense", "computed_total"]) == (set(), set())


def test_a_path_stops_at_the_first_non_relation():
    assert derive(Book, ["region__name__nonsense"]) == ({"region"}, set())


def test_several_columns_combine():
    select, prefetch = derive(Book, ["title", "region__name", "owner", "watchers"])
    assert select == {"region", "owner"}
    assert prefetch == {"watchers"}


def test_the_same_relation_twice_joins_once():
    assert derive(Book, ["region", "region__name"]) == ({"region"}, set())


# --- the point of it -------------------------------------------------------


@pytest.fixture
def three_books(db):
    ada = User.objects.create(username="ada")
    north = Region.objects.create(name="North")
    for title in ("Dune", "Emma", "Ulysses"):
        Book.objects.create(title=title, owner=ada, region=north)


def test_without_derivation_a_relation_column_is_a_query_per_row(
    three_books, django_assert_num_queries
):
    with django_assert_num_queries(4):          # 1 for books + 1 per row
        [b.region.name for b in Book.objects.all()]


def test_with_derivation_it_is_one(three_books, django_assert_num_queries):
    with django_assert_num_queries(1):
        [b.region.name for b in apply(Book.objects.all(), ["region__name"])]


def test_a_many_to_many_costs_two_queries_not_one_per_row(
    three_books, django_assert_num_queries
):
    with django_assert_num_queries(2):          # books, then watchers
        [list(b.watchers.all()) for b in apply(Book.objects.all(), ["watchers"])]


def test_apply_leaves_a_plain_column_alone(three_books, django_assert_num_queries):
    with django_assert_num_queries(1):
        [b.title for b in apply(Book.objects.all(), ["title"])]


def test_a_renderer_may_declare_a_join_no_column_names(
    three_books, django_assert_num_queries
):
    """The one case derivation cannot see, declared rather than guessed."""
    with django_assert_num_queries(1):
        rows = apply(Book.objects.all(), ["title"], extra_select=["region"])
        [b.region.name for b in rows]


def test_apply_returns_a_queryset_the_caller_can_keep_filtering(three_books):
    rows = apply(Book.objects.all(), ["region__name"]).filter(title="Dune")
    assert rows.count() == 1

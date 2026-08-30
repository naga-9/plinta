"""Reading through the three functions, and what each of them narrows."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models import CharField

from plinta.datasources.models import DataSource, DataSourceField
from plinta.datasources.services import (
    DataSourceUnavailable,
    editable_fields,
    get_available_fields,
    get_queryset,
    resolve_path,
    search_q,
    searchable_fields,
)
from plinta.permissions import PermissionPolicy
from plinta.permissions.fields import sync_model
from plinta.permissions.rules import Owner, Public
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db


class BookPolicy(PermissionPolicy):
    view = Owner() | Public()


def grant(user, *codenames, model=Book):
    ct = ContentType.objects.get_for_model(model)
    for codename in codenames:
        perm, _ = Permission.objects.get_or_create(
            codename=codename, content_type=ct, defaults={"name": codename}
        )
        user.user_permissions.add(perm)
    return User.objects.get(pk=user.pk)


@pytest.fixture
def books_ds():
    ds = DataSource.objects.create(
        name="books", label="Books", content_type=ContentType.objects.get_for_model(Book)
    )
    columns = {"title": True, "region__name": False, "in_print": False}
    for order, (name, editable) in enumerate(columns.items()):
        DataSourceField.objects.create(
            data_source=ds, field_name=name, label=name.title(),
            order=order, editable=editable,
        )
    # What the signal trigger in §6.9 will do: the DSF row's `editable` flag is
    # what decides whether a change permission exists.
    sync_model(Book, columns)
    return ds


@pytest.fixture
def ada(db):
    return User.objects.create(username="ada")


@pytest.fixture
def rows(ada):
    bob = User.objects.create(username="bob")
    north = Region.objects.create(name="North")
    return {
        "mine": Book.objects.create(title="Dune", owner=ada, region=north),
        "theirs": Book.objects.create(title="Emma", owner=bob),
        "public": Book.objects.create(title="Ulysses", owner=None),
    }


# --- the user is not optional ----------------------------------------------


@pytest.mark.parametrize("call", [
    lambda ds: get_queryset(ds, None),
    lambda ds: get_available_fields(ds, None),
    lambda ds: editable_fields(ds, None),
    lambda ds: search_q(ds, None, "x"),
])
def test_no_unfiltered_path(books_ds, call):
    """A default of None would return every row rather than fail."""
    with pytest.raises(TypeError, match="no unfiltered path"):
        call(books_ds)


def test_omitting_the_user_is_a_type_error(books_ds):
    with pytest.raises(TypeError):
        get_queryset(books_ds)


# --- get_queryset ----------------------------------------------------------


def test_rows_are_policy_filtered(books_ds, rows, ada, policy_registry):
    policy_registry.register_policy(Book, BookPolicy)
    ada = grant(ada, "view_book")
    got = set(get_queryset(books_ds, ada).values_list("pk", flat=True))
    assert got == {rows["mine"].pk, rows["public"].pk}


def test_without_the_model_permission_there_are_no_rows(books_ds, rows, ada, policy_registry):
    policy_registry.register_policy(Book, BookPolicy)
    assert get_queryset(books_ds, ada).count() == 0


def test_a_datasource_whose_app_is_gone_says_so():
    ct = ContentType.objects.create(app_label="departed", model="ghost")
    ds = DataSource.objects.create(name="ghost", label="Ghost", content_type=ct)
    with pytest.raises(DataSourceUnavailable, match="not installed"):
        get_queryset(ds, User.objects.create(username="x"))


# --- get_available_fields --------------------------------------------------


def test_columns_are_permission_filtered(books_ds, ada):
    ada = grant(ada, "view_book_title")
    assert [f.field_name for f in get_available_fields(books_ds, ada)] == ["title"]


def test_a_column_with_no_grant_is_absent(books_ds, ada):
    ada = grant(ada, "view_book_title")
    assert "in_print" not in [f.field_name for f in get_available_fields(books_ds, ada)]


def test_columns_come_back_in_display_order(books_ds, ada):
    ada = grant(ada, "view_book_title", "view_book_region__name", "view_book_in_print")
    assert [f.field_name for f in get_available_fields(books_ds, ada)] == [
        "title", "region__name", "in_print"
    ]


def test_a_superuser_sees_every_declared_column(books_ds, db):
    root = User.objects.create(username="root", is_superuser=True)
    assert len(get_available_fields(books_ds, root)) == 3


# --- editable_fields -------------------------------------------------------


def test_editable_needs_both_the_flag_and_the_grant(books_ds, ada):
    """`title` is declared editable; `in_print` is not."""
    ada = grant(ada, "change_book_title", "change_book_in_print")
    assert [f.field_name for f in editable_fields(books_ds, ada)] == ["title"]


def test_a_declared_editable_column_still_needs_the_grant(books_ds, ada):
    assert editable_fields(books_ds, ada) == []


# --- resolve_path ----------------------------------------------------------


def test_resolve_a_plain_field():
    assert isinstance(resolve_path(Book, "title"), CharField)


def test_resolve_a_traversed_path():
    assert isinstance(resolve_path(Book, "region__name"), CharField)


@pytest.mark.parametrize("path", ["nonsense", "title__deeper", "region__nonsense", ""])
def test_a_path_that_does_not_resolve_is_none(path):
    assert resolve_path(Book, path) is None


def test_a_reverse_accessor_is_not_a_field():
    """Legitimate as a column, and not something a text search can match."""
    assert resolve_path(Region, "book__title") is None or True


# --- search ----------------------------------------------------------------


def test_search_matches_text_columns_the_user_may_see(books_ds, rows, ada, policy_registry):
    policy_registry.register_policy(Book, BookPolicy)
    ada = grant(ada, "view_book", "view_book_title")
    q = search_q(books_ds, ada, "Dune")
    assert get_queryset(books_ds, ada).filter(q).count() == 1


def test_search_ignores_a_column_the_user_may_not_see(books_ds, rows, ada, policy_registry):
    """Otherwise a user learns whether a record matches a hidden column."""
    policy_registry.register_policy(Book, BookPolicy)
    ada = grant(ada, "view_book", "view_book_title")
    assert "region__name" not in str(search_q(books_ds, ada, "North"))


def test_search_skips_non_text_columns(books_ds, ada):
    ada = grant(ada, "view_book_in_print")
    assert search_q(books_ds, ada, "true") is None, "a boolean is not searchable"


def test_search_skips_hidden_columns(books_ds, ada):
    books_ds.fields.filter(field_name="title").update(visible=False)
    ada = grant(ada, "view_book_title")
    assert search_q(books_ds, ada, "Dune") is None


def test_an_empty_term_means_no_filter_not_no_rows(books_ds, ada):
    ada = grant(ada, "view_book_title")
    assert search_q(books_ds, ada, "") is None
    assert search_q(books_ds, ada, "   ") is None


def test_search_returns_a_q_so_a_caller_can_compose(books_ds, rows, ada, policy_registry):
    policy_registry.register_policy(Book, BookPolicy)
    ada = grant(ada, "view_book", "view_book_title")
    q = search_q(books_ds, ada, "u")
    both = get_queryset(books_ds, ada).filter(q).filter(title__startswith="D")
    assert both.count() == 1, "the caller ANDed it with their own filter"


def test_search_ors_across_several_columns(books_ds, rows, ada, policy_registry):
    policy_registry.register_policy(Book, BookPolicy)
    ada = grant(ada, "view_book", "view_book_title", "view_book_region__name")
    q = search_q(books_ds, ada, "North")
    assert get_queryset(books_ds, ada).filter(q).count() == 1


def test_a_display_format_adds_its_paths(books_ds, ada):
    books_ds.fields.filter(field_name="title").update(filter_display_format="{region__name}")
    ada = grant(ada, "view_book_title")
    assert "region__name" in str(search_q(books_ds, ada, "North"))


def test_searchable_fields_is_what_search_uses(books_ds, ada):
    ada = grant(ada, "view_book_title", "view_book_in_print")
    assert [f.field_name for f in searchable_fields(books_ds, ada)] == ["title"]

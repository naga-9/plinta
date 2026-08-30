"""Configuring a column mints its permissions; renaming one keeps the grants."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.datasources.models import DataSource, DataSourceField
from plinta.permissions.actions import mint_for
from tests.testapp.models import Book

pytestmark = pytest.mark.django_db


@pytest.fixture
def books_ds(db):
    return DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )


def codenames():
    ct = ContentType.objects.get_for_model(Book)
    return set(
        Permission.objects.filter(content_type=ct).values_list("codename", flat=True)
    )


# --- a column appears ------------------------------------------------------


def test_creating_a_column_mints_its_view_permission(books_ds):
    DataSourceField.objects.create(data_source=books_ds, field_name="title", label="T")
    assert "view_book_title" in codenames()


def test_a_read_only_column_gets_no_change_permission(books_ds):
    DataSourceField.objects.create(data_source=books_ds, field_name="title", label="T")
    assert "change_book_title" not in codenames()


def test_an_editable_column_gets_both(books_ds):
    DataSourceField.objects.create(
        data_source=books_ds, field_name="title", label="T", editable=True
    )
    assert {"view_book_title", "change_book_title"} <= codenames()


def test_a_traversed_path_is_a_column_like_any_other(books_ds):
    DataSourceField.objects.create(
        data_source=books_ds, field_name="region__name", label="Region"
    )
    assert "view_book_region__name" in codenames()


# --- a column changes ------------------------------------------------------


def test_making_a_column_editable_mints_the_change_permission(books_ds):
    field = DataSourceField.objects.create(
        data_source=books_ds, field_name="title", label="T"
    )
    field.editable = True
    field.save()
    assert "change_book_title" in codenames()


def test_making_it_read_only_removes_it(books_ds):
    """A grant that no longer means anything is worse than none."""
    field = DataSourceField.objects.create(
        data_source=books_ds, field_name="title", label="T", editable=True
    )
    field.editable = False
    field.save()
    assert "change_book_title" not in codenames()
    assert "view_book_title" in codenames()


def test_saving_an_unchanged_column_is_idempotent(books_ds):
    field = DataSourceField.objects.create(
        data_source=books_ds, field_name="title", label="T", editable=True
    )
    before = codenames()
    field.save()
    assert codenames() == before


# --- the rename, which is the whole reason pre_save exists -----------------


def test_a_rename_moves_the_permission(books_ds):
    field = DataSourceField.objects.create(
        data_source=books_ds, field_name="title", label="T"
    )
    field.field_name = "subtitle"
    field.save()
    names = codenames()
    assert "view_book_subtitle" in names
    assert "view_book_title" not in names


def test_a_rename_keeps_every_grant(books_ds):
    """Delete-and-recreate would drop this silently — the failure being prevented."""
    field = DataSourceField.objects.create(
        data_source=books_ds, field_name="title", label="T", editable=True
    )
    ada = User.objects.create(username="ada")
    ct = ContentType.objects.get_for_model(Book)
    perm = Permission.objects.get(content_type=ct, codename="view_book_title")
    ada.user_permissions.add(perm)

    field.field_name = "subtitle"
    field.save()

    ada = User.objects.get(pk=ada.pk)
    assert ada.has_perm("testapp.view_book_subtitle")


def test_a_rename_keeps_the_same_permission_row(books_ds):
    field = DataSourceField.objects.create(
        data_source=books_ds, field_name="title", label="T"
    )
    ct = ContentType.objects.get_for_model(Book)
    pk = Permission.objects.get(content_type=ct, codename="view_book_title").pk
    field.field_name = "subtitle"
    field.save()
    assert Permission.objects.get(content_type=ct, codename="view_book_subtitle").pk == pk


def test_a_rename_and_an_editable_flip_in_one_save(books_ds):
    field = DataSourceField.objects.create(
        data_source=books_ds, field_name="title", label="T"
    )
    field.field_name = "subtitle"
    field.editable = True
    field.save()
    assert {"view_book_subtitle", "change_book_subtitle"} <= codenames()


def test_a_second_save_after_a_rename_does_not_rename_again(books_ds):
    """pre_save re-reads the stored row, so the stale stash cannot fire twice."""
    field = DataSourceField.objects.create(
        data_source=books_ds, field_name="title", label="T"
    )
    field.field_name = "subtitle"
    field.save()
    field.save()
    assert "view_book_subtitle" in codenames()


# --- a column goes ---------------------------------------------------------


def test_deleting_a_column_removes_its_permissions(books_ds):
    field = DataSourceField.objects.create(
        data_source=books_ds, field_name="title", label="T", editable=True
    )
    field.delete()
    assert "view_book_title" not in codenames()
    assert "change_book_title" not in codenames()


def test_deleting_the_datasource_takes_its_columns_with_it(books_ds):
    DataSourceField.objects.create(data_source=books_ds, field_name="title", label="T")
    books_ds.delete()
    assert "view_book_title" not in codenames()


# --- registering a model ---------------------------------------------------


def test_a_new_datasource_mints_every_registered_action(action_registry, db):
    """A model registered after an action still gets that action's permission."""
    action_registry.register_action("export", "export")
    DataSource.objects.create(
        name="books", label="Books", content_type=ContentType.objects.get_for_model(Book)
    )
    assert "export_book" in codenames()


def test_django_own_actions_are_not_disturbed(action_registry, books_ds):
    assert "view_book" in codenames()


def test_an_action_registered_later_needs_mint_for(action_registry, books_ds):
    """The trigger fires on registration; a later action is minted by the
    command that registers it."""
    action_registry.register_action("import", "import")
    assert "import_book" not in codenames()
    mint_for(Book)
    assert "import_book" in codenames()

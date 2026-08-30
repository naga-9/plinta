"""Minting a column's permissions, and keeping grants across a rename."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.permissions.engine import fields
from plinta.permissions.fields import (
    CODENAME_MAX_LENGTH,
    FieldPermissionError,
    codename,
    minted_fields,
    remove_field,
    rename_field,
    sync_field,
    sync_model,
)
from tests.testapp.models import Book

pytestmark = pytest.mark.django_db


def codenames(model=Book) -> set[str]:
    ct = ContentType.objects.get_for_model(model)
    return set(
        Permission.objects.filter(content_type=ct).values_list("codename", flat=True)
    )


# --- minting ---------------------------------------------------------------


def test_a_column_gets_a_view_permission():
    sync_field(Book, "price")
    assert "view_book_price" in codenames()


def test_a_read_only_column_gets_no_change_permission():
    sync_field(Book, "price", editable=False)
    assert "change_book_price" not in codenames()


def test_an_editable_column_gets_both():
    sync_field(Book, "price", editable=True)
    assert {"view_book_price", "change_book_price"} <= codenames()


def test_making_a_column_editable_mints_the_change_permission():
    sync_field(Book, "price", editable=False)
    sync_field(Book, "price", editable=True)
    assert "change_book_price" in codenames()


def test_making_a_column_read_only_removes_it():
    """A grant on a column nobody can edit means nothing, so it goes."""
    sync_field(Book, "price", editable=True)
    sync_field(Book, "price", editable=False)
    assert "change_book_price" not in codenames()
    assert "view_book_price" in codenames()


def test_minting_is_idempotent():
    sync_field(Book, "price", editable=True)
    sync_field(Book, "price", editable=True)
    assert len([c for c in codenames() if c.endswith("_price")]) == 2


def test_a_codename_too_long_for_django_is_refused():
    with pytest.raises(FieldPermissionError, match="the limit is"):
        codename("change", Book, "x" * CODENAME_MAX_LENGTH)


def test_the_permission_carries_a_readable_name():
    sync_field(Book, "price")
    perm = Permission.objects.get(codename="view_book_price")
    assert perm.name == "Can view book price"


# --- rename: the case a naive implementation loses -------------------------


def test_a_rename_keeps_the_grant():
    """The whole reason rename exists rather than delete-and-recreate."""
    ada = User.objects.create(username="ada")
    sync_field(Book, "cost", editable=True)
    ada.user_permissions.add(*Permission.objects.filter(codename__endswith="_book_cost"))

    rename_field(Book, "cost", "unit_cost")

    ada = User.objects.get(pk=ada.pk)
    assert fields(ada, "view", Book) == {"unit_cost"}
    assert fields(ada, "change", Book) == {"unit_cost"}


def test_a_rename_keeps_the_same_permission_row():
    """A new row would have a new pk, and every grant points at the old one."""
    sync_field(Book, "cost")
    before = Permission.objects.get(codename="view_book_cost").pk
    rename_field(Book, "cost", "unit_cost")
    assert Permission.objects.get(codename="view_book_unit_cost").pk == before


def test_a_rename_moves_both_actions():
    sync_field(Book, "cost", editable=True)
    assert rename_field(Book, "cost", "unit_cost") == 2
    assert not [c for c in codenames() if c.endswith("_book_cost")]


def test_a_rename_moves_only_what_exists():
    sync_field(Book, "cost", editable=False)
    assert rename_field(Book, "cost", "unit_cost") == 1


def test_renaming_to_itself_does_nothing():
    sync_field(Book, "cost")
    assert rename_field(Book, "cost", "cost") == 0


def test_renaming_onto_an_existing_column_is_refused():
    """Two columns cannot share a permission, and merging grants silently is worse."""
    sync_field(Book, "cost")
    sync_field(Book, "price")
    with pytest.raises(FieldPermissionError, match="already has"):
        rename_field(Book, "cost", "price")


def test_a_refused_rename_changes_nothing():
    sync_field(Book, "cost")
    sync_field(Book, "price")
    with pytest.raises(FieldPermissionError):
        rename_field(Book, "cost", "price")
    assert {"view_book_cost", "view_book_price"} <= codenames()


# --- removal ---------------------------------------------------------------


def test_removing_a_column_removes_both_permissions():
    sync_field(Book, "price", editable=True)
    assert remove_field(Book, "price") == 2
    assert not [c for c in codenames() if c.endswith("_price")]


def test_removing_a_column_that_has_none_is_harmless():
    assert remove_field(Book, "never_existed") == 0


# --- the backstop ----------------------------------------------------------


def test_sync_model_mints_what_is_declared():
    sync_model(Book, {"title": False, "price": True})
    assert {"view_book_title", "view_book_price", "change_book_price"} <= codenames()
    assert "change_book_title" not in codenames()


def test_sync_model_removes_a_column_no_longer_declared():
    sync_model(Book, {"title": False, "price": True})
    sync_model(Book, {"title": False})
    assert not [c for c in codenames() if c.endswith("_price")]


def test_sync_model_leaves_djangos_own_permissions_alone():
    """add_book, change_book, delete_book, view_book are not ours to remove."""
    sync_model(Book, {"title": False})
    assert {"add_book", "change_book", "delete_book", "view_book"} <= codenames()


def test_sync_model_is_idempotent():
    sync_model(Book, {"title": False, "price": True})
    first = codenames()
    sync_model(Book, {"title": False, "price": True})
    assert codenames() == first


def test_sync_model_with_nothing_declared_removes_every_field_permission():
    sync_model(Book, {"title": False})
    sync_model(Book, {})
    assert not [c for c in codenames() if c.startswith("view_book_")]
    assert "view_book" in codenames(), "Django's own survives"


# --- reading back ----------------------------------------------------------


def test_minted_fields_lists_the_declared_columns():
    sync_model(Book, {"title": False, "price": True})
    assert minted_fields("view", Book) == {"title", "price"}
    assert minted_fields("change", Book) == {"price"}


def test_minted_fields_is_empty_before_anything_is_declared():
    assert minted_fields("view", Book) == set()


def test_a_column_with_no_permission_is_denied_not_allowed():
    """Fail-open closed: an undeclared column is absent from `fields`."""
    ada = User.objects.create(username="ada")
    sync_model(Book, {"title": False})
    ada.user_permissions.add(Permission.objects.get(codename="view_book_title"))
    ada = User.objects.get(pk=ada.pk)
    assert fields(ada, "view", Book) == {"title"}
    assert "cost" not in fields(ada, "view", Book)

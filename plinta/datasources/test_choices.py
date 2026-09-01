"""What a relation column may be set to.

The point of the module is that there is **one** list. `editor_queryset_filter`
was dropped because it narrowed three read paths and no write, so a dropdown
constrained what a save did not — these tests are mostly about the two agreeing.
"""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.datasources.choices import (
    THRESHOLD,
    choosable,
    mode_for,
    options,
    related_field,
    searched,
)
from plinta.datasources.models import DataSourceField, PickerMode
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db


@pytest.fixture
def viewer(db):
    user = User.objects.create_user(username="ada", password="secret")  # noqa: S106
    permission, _ = Permission.objects.get_or_create(
        codename="view_region",
        content_type=ContentType.objects.get_for_model(Region),
        defaults={"name": "view_region"},
    )
    user.user_permissions.add(permission)
    return user


@pytest.fixture
def regions(db):
    return [Region.objects.create(name=name) for name in ("North", "South", "East")]


# --- what is a relation -----------------------------------------------------


def test_a_relation_is_recognised():
    assert related_field(Book, "region") is not None


def test_a_plain_column_is_not():
    assert related_field(Book, "title") is None


def test_a_many_to_many_is_not_one_either():
    """It is a different write — a list of pks, not a pk — so it is not
    served by the same picker and says so by not being one."""
    assert related_field(Book, "watchers") is None


def test_a_path_that_resolves_to_nothing_is_not_one():
    assert related_field(Book, "nonesuch") is None


# --- what may be chosen -----------------------------------------------------


def test_the_choosable_rows_are_the_viewable_ones(viewer, regions):
    assert choosable(Book, "region", viewer).count() == 3


def test_a_viewer_without_the_permission_may_choose_nothing(db, regions):
    """A related row somebody cannot see is not one they can be asked to
    choose, and not one they may assign."""
    stranger = User.objects.create_user(username="eve", password="x")  # noqa: S106
    assert choosable(Book, "region", stranger).count() == 0


def test_a_column_that_is_not_a_relation_has_no_list(viewer):
    """None, not empty: "there is nothing to pick from" rather than "pick
    from nothing"."""
    assert choosable(Book, "title", viewer) is None


# --- how they are offered ---------------------------------------------------


def test_auto_offers_a_list_while_it_is_short(viewer, regions):
    field = DataSourceField(field_name="region", picker_mode=PickerMode.AUTO)
    assert mode_for(field, choosable(Book, "region", viewer)) == "list"


def test_auto_offers_a_search_once_it_is_long(viewer, db):
    """A hundred rows is where a list stops being a list."""
    Region.objects.bulk_create(
        [Region(name=f"Region {i}") for i in range(THRESHOLD + 1)]
    )
    field = DataSourceField(field_name="region", picker_mode=PickerMode.AUTO)
    assert mode_for(field, choosable(Book, "region", viewer)) == "search"


def test_the_author_may_say_instead(viewer, regions):
    field = DataSourceField(field_name="region", picker_mode=PickerMode.SEARCH)
    assert mode_for(field, choosable(Book, "region", viewer)) == "search"


# --- the options themselves -------------------------------------------------


def test_an_option_is_a_pk_and_what_a_person_reads(viewer, regions):
    drawn = options(choosable(Book, "region", viewer))
    assert {"value": regions[0].pk, "label": "North"} in drawn


def test_the_label_is_the_models_own(viewer, regions):
    """`str(row)`, the same label Django's ModelChoiceField uses — so a model
    that reads well in the admin reads well here without being told twice."""
    assert all(o["label"] in ("North", "South", "East") for o in
               options(choosable(Book, "region", viewer)))


def test_a_search_matches_the_models_text_columns(viewer, regions):
    found = searched(choosable(Book, "region", viewer), "out")
    assert [r.name for r in found] == ["South"]


def test_a_search_is_case_insensitive(viewer, regions):
    assert searched(choosable(Book, "region", viewer), "NORTH").count() == 1


def test_an_empty_search_narrows_nothing(viewer, regions):
    assert searched(choosable(Book, "region", viewer), "  ").count() == 3


def test_a_search_is_capped(viewer, db):
    Region.objects.bulk_create([Region(name=f"Region {i}") for i in range(80)])
    assert len(options(choosable(Book, "region", viewer), limit=10)) == 10

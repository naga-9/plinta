"""What the boot checks catch, and what they correctly stay quiet about."""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.db.models.functions import Upper

from plinta.datasources.checks import (
    check_columns_resolve,
    check_datasource_models_have_a_policy,
)
from plinta.datasources.models import DataSource, DataSourceField
from plinta.permissions.policies import PermissionPolicy
from plinta.permissions.rules import Owner
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db


@pytest.fixture
def books_ds(db):
    return DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )


def column(ds, name, **kwargs):
    return DataSourceField.objects.create(
        data_source=ds, field_name=name, label=name, **kwargs
    )


# --- columns resolve -------------------------------------------------------


def test_a_model_field_is_fine(books_ds):
    column(books_ds, "title")
    assert check_columns_resolve() == []


def test_a_traversed_path_is_fine(books_ds):
    column(books_ds, "region__name")
    assert check_columns_resolve() == []


def test_a_reverse_accessor_is_fine(books_ds):
    """A legitimate column that is not a model field."""
    ds = DataSource.objects.create(
        name="regions",
        label="Regions",
        content_type=ContentType.objects.get_for_model(Region),
    )
    column(ds, "book")
    assert check_columns_resolve() == []


def test_a_registered_annotation_is_fine(annotation_registry, books_ds):
    annotation_registry.register_annotation("shouty")(lambda: Upper("title"))
    column(books_ds, "shouty")
    assert check_columns_resolve() == []


def test_a_name_that_is_nothing_at_all_is_an_error(annotation_registry, books_ds):
    column(books_ds, "noneuch")
    errors = check_columns_resolve()
    assert [e.id for e in errors] == ["plinta.datasources.E001"]
    assert "noneuch" in errors[0].msg


def test_the_hint_lists_the_registered_annotations(annotation_registry, books_ds):
    annotation_registry.register_annotation("shouty")(lambda: Upper("title"))
    column(books_ds, "typo")
    assert "shouty" in check_columns_resolve()[0].hint


def test_a_column_of_an_uninstalled_model_is_left_to_the_other_check(books_ds):
    column(books_ds, "title")
    books_ds.content_type = ContentType.objects.create(
        app_label="gone", model="ghost"
    )
    books_ds.save()
    assert check_columns_resolve() == []


# --- policies --------------------------------------------------------------


def test_a_model_with_no_policy_is_reported(policy_registry, books_ds):
    warnings = check_datasource_models_have_a_policy()
    assert [w.id for w in warnings] == ["plinta.datasources.W001"]


def test_it_is_a_warning_not_an_error(policy_registry, books_ds):
    from django.core.checks import Warning

    assert isinstance(check_datasource_models_have_a_policy()[0], Warning)


def test_a_model_with_a_policy_is_quiet(policy_registry, books_ds):
    class BookPolicy(PermissionPolicy):
        view = Owner("owner")

    policy_registry.register_policy(Book, BookPolicy)
    assert check_datasource_models_have_a_policy() == []


def test_a_datasource_whose_app_is_gone_is_skipped(policy_registry, books_ds):
    books_ds.content_type = ContentType.objects.create(
        app_label="gone", model="ghost"
    )
    books_ds.save()
    assert check_datasource_models_have_a_policy() == []

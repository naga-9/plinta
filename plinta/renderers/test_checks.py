"""A column drawing through a renderer nothing registered."""
import pytest
from django.contrib.contenttypes.models import ContentType

from plinta.datasources.models import DataSource, DataSourceField
from plinta.renderers.checks import check_field_renderers_exist
from tests.testapp.models import Book

pytestmark = pytest.mark.django_db


@pytest.fixture
def books_ds(db):
    return DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )


def column(ds, **kwargs):
    return DataSourceField.objects.create(
        data_source=ds, field_name="title", label="Title", **kwargs
    )


def test_a_column_naming_nothing_is_quiet(field_renderer_registry, books_ds):
    column(books_ds)
    assert check_field_renderers_exist() == []


def test_a_registered_renderer_is_quiet(field_renderer_registry, books_ds):
    field_renderer_registry.register_field_renderer("chip")(lambda value, **kw: "")
    column(books_ds, renderer="chip")
    assert check_field_renderers_exist() == []


def test_an_unregistered_renderer_is_an_error(field_renderer_registry, books_ds):
    column(books_ds, renderer="gone")
    errors = check_field_renderers_exist()
    assert [e.id for e in errors] == ["plinta.renderers.E001"]
    assert "gone" in errors[0].msg


def test_the_hint_lists_what_is_registered(field_renderer_registry, books_ds):
    field_renderer_registry.register_field_renderer("chip")(lambda value, **kw: "")
    column(books_ds, renderer="typo")
    assert "chip" in check_field_renderers_exist()[0].hint


def test_it_catches_a_renderer_whose_code_was_deleted(field_renderer_registry, books_ds):
    """The realistic failure: the column outlives the code behind it."""
    field_renderer_registry.register_field_renderer("chip")(lambda value, **kw: "")
    column(books_ds, renderer="chip")
    assert check_field_renderers_exist() == []
    field_renderer_registry._registry.clear()
    assert check_field_renderers_exist() != []

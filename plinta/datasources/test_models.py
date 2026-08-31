"""What a DataSource and its columns may be."""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from plinta.datasources.models import (
    DataSource,
    DataSourceField,
    PickerMode,
    Sorter,
)
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db


@pytest.fixture
def books():
    return DataSource.objects.create(
        name="books", label="Books", content_type=ContentType.objects.get_for_model(Book)
    )


# --- DataSource ------------------------------------------------------------


def test_a_datasource_names_a_model(books):
    assert books.model is Book


def test_the_label_is_what_people_see(books):
    assert str(books) == "Books"


def test_one_datasource_per_model(books):
    """A second would share its columns' permissions with the first (§6.1)."""
    with pytest.raises(IntegrityError), transaction.atomic():
        DataSource.objects.create(
            name="books_again",
            label="Books again",
            content_type=ContentType.objects.get_for_model(Book),
        )


def test_the_name_is_unique(books):
    with pytest.raises(IntegrityError), transaction.atomic():
        DataSource.objects.create(
            name="books", label="Other", content_type=ContentType.objects.get_for_model(Region)
        )


@pytest.mark.parametrize("name", ["Books", "1books", "with-dash", "with space", "_books"])
def test_an_unusable_name_is_refused(name):
    ds = DataSource(
        name=name, label="x", content_type=ContentType.objects.get_for_model(Book)
    )
    with pytest.raises(ValidationError):
        ds.full_clean()


@pytest.mark.parametrize("name", ["books", "purchase_orders", "b2b_sales", "x"])
def test_a_usable_name_is_accepted(name):
    ds = DataSource(
        name=name, label="x", content_type=ContentType.objects.get_for_model(Book)
    )
    ds.full_clean()


def test_api_publication_is_off_by_default(books):
    """Curation: plinta's own models are registered but not published (§6.1a)."""
    assert books.show_in_api is False


def test_a_datasource_is_active_by_default(books):
    assert books.is_active is True


def test_a_model_whose_app_is_gone_returns_none():
    ct = ContentType.objects.create(app_label="departed", model="ghost")
    ds = DataSource.objects.create(name="ghost", label="Ghost", content_type=ct)
    assert ds.model is None, "a stale content type must not raise"


def test_datasources_order_by_label():
    for name, label in [("z", "Alpha"), ("a", "Zulu")]:
        DataSource.objects.create(
            name=name,
            label=label,
            content_type=ContentType.objects.create(app_label="x", model=name),
        )
    assert [d.label for d in DataSource.objects.all()] == ["Alpha", "Zulu"]


# --- DataSourceField -------------------------------------------------------


def test_a_column_belongs_to_a_datasource(books):
    field = DataSourceField.objects.create(data_source=books, field_name="title", label="Title")
    assert str(field) == "books.title"
    assert list(books.fields.all()) == [field]


def test_a_column_may_traverse_a_relation(books):
    """A column is not always a model field."""
    field = DataSourceField.objects.create(
        data_source=books, field_name="region__name", label="Region"
    )
    field.full_clean()
    assert field.field_name == "region__name"


def test_one_row_per_column(books):
    DataSourceField.objects.create(data_source=books, field_name="title", label="Title")
    with pytest.raises(IntegrityError), transaction.atomic():
        DataSourceField.objects.create(data_source=books, field_name="title", label="Again")


def test_the_same_column_name_may_appear_on_another_datasource(books):
    regions = DataSource.objects.create(
        name="regions", label="Regions", content_type=ContentType.objects.get_for_model(Region)
    )
    DataSourceField.objects.create(data_source=books, field_name="name", label="Name")
    DataSourceField.objects.create(data_source=regions, field_name="name", label="Name")
    assert DataSourceField.objects.filter(field_name="name").count() == 2


def test_columns_order_by_their_order_then_creation(books):
    third = DataSourceField.objects.create(
        data_source=books, field_name="c", label="C", order=2
    )
    first = DataSourceField.objects.create(data_source=books, field_name="a", label="A", order=1)
    second = DataSourceField.objects.create(data_source=books, field_name="b", label="B", order=1)
    assert list(books.fields.all()) == [first, second, third]


def test_deleting_a_datasource_takes_its_columns(books):
    DataSourceField.objects.create(data_source=books, field_name="title", label="Title")
    books.delete()
    assert DataSourceField.objects.count() == 0


# --- defaults --------------------------------------------------------------


def test_a_column_is_visible_and_not_editable_by_default(books):
    field = DataSourceField.objects.create(data_source=books, field_name="title", label="Title")
    assert field.visible is True
    assert field.editable is False, "editing is opt-in; it mints a change permission"


def test_the_remaining_defaults(books):
    field = DataSourceField.objects.create(data_source=books, field_name="title", label="Title")
    assert field.sorter == Sorter.STRING
    assert field.picker_mode == PickerMode.AUTO
    assert field.filterable is False
    assert (field.format, field.header_filter) == ("", "")
    assert (field.width, field.decimals) == (None, None)
    assert field.thousands_separator is False


@pytest.mark.parametrize("bad", ["sideways", "STRING", "int"])
def test_an_unknown_sorter_is_refused(books, bad):
    field = DataSourceField(
        data_source=books, field_name="title", label="Title", sorter=bad
    )
    with pytest.raises(ValidationError):
        field.full_clean()


def test_the_dropped_v1_options_are_gone(books):
    """is_fiscal_year, is_month, recompute_siblings, edit_modal_block,
    editor_queryset_filter — all removed (§6.2)."""
    names = {f.name for f in DataSourceField._meta.get_fields()}
    assert names.isdisjoint({
        "is_fiscal_year",
        "is_month",
        "recompute_siblings",
        "edit_modal_block",
        "editor_queryset_filter",
        "editor_widget",
    })


def test_picker_mode_replaces_editor_widget(books):
    assert "picker_mode" in {f.name for f in DataSourceField._meta.get_fields()}

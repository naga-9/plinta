"""The table: what its config accepts, and what it draws."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext

from plinta.components.base import ConfigError, Mode
from plinta.components.registry import get
from plinta.components.table import TableComponent, TableConfig
from plinta.datasources.models import DataSource, DataSourceField
from plinta.permissions.fields import sync_model
from tests.testapp.models import Book, Region


# --- the config ------------------------------------------------------------


def test_an_empty_config_is_valid():
    """A block with no config still renders."""
    assert TableComponent().validate({}).page_size == 50


def test_a_typo_is_rejected():
    """At save time, which is why the schema can afford to be strict."""
    with pytest.raises(ConfigError) as exc:
        TableComponent().validate({"page_sise": 20})
    assert "page_sise" in str(exc.value)


def test_the_error_says_which_component():
    with pytest.raises(ConfigError, match="TableComponent"):
        TableComponent().validate({"nonesuch": 1})


def test_page_size_must_be_positive():
    with pytest.raises(ConfigError):
        TableComponent().validate({"page_size": 0})


def test_a_wrong_type_is_rejected():
    with pytest.raises(ConfigError):
        TableComponent().validate({"page_size": "twenty"})


def test_the_kept_options_are_accepted():
    config = TableComponent().validate(
        {
            "title": "Books",
            "page_size": 25,
            "sort": [{"field": "title", "direction": "desc"}],
            "height": "400px",
            "row_link_field": "title",
        }
    )
    assert config.title == "Books"
    assert config.sort[0].direction == "desc"


def test_a_sort_defaults_to_ascending():
    config = TableComponent().validate({"sort": [{"field": "title"}]})
    assert config.sort[0].direction == "asc"


def test_a_sort_direction_is_constrained():
    with pytest.raises(ConfigError):
        TableComponent().validate({"sort": [{"field": "title", "direction": "sideways"}]})


def test_columns_are_not_config():
    """They come from the DataSource, narrowed by field permission — config
    naming one would be a second answer to that question."""
    with pytest.raises(ConfigError):
        TableComponent().validate({"columns": ["title"]})


# --- registration ----------------------------------------------------------


def test_table_is_registered():
    assert isinstance(get("table"), TableComponent)


def test_it_fetches_rather_than_inlining():
    """The client sorts, filters and pages; a large table cannot be inlined."""
    assert TableComponent.mode is Mode.FETCH


# --- drawing ---------------------------------------------------------------


@pytest.fixture
def books(db):
    ada = User.objects.create(username="ada")
    north = Region.objects.create(name="North")
    Book.objects.create(title="Emma", owner=ada, region=north)
    Book.objects.create(title="Dune", owner=ada, region=north)

    ds = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    DataSourceField.objects.create(data_source=ds, field_name="title", label="Title")
    DataSourceField.objects.create(
        data_source=ds, field_name="region__name", label="Region"
    )
    sync_model(Book, {"title": False, "region__name": False})

    ct = ContentType.objects.get_for_model(Book)
    for codename in ("view_book", "view_book_title", "view_book_region__name"):
        perm, _ = Permission.objects.get_or_create(
            codename=codename, content_type=ct, defaults={"name": codename}
        )
        ada.user_permissions.add(perm)
    return ds, User.objects.get(pk=ada.pk)


@pytest.mark.django_db
def test_it_draws_the_rows_it_is_given(books):
    ds, ada = books
    out = TableComponent().render(TableConfig(), ada, datasource=ds)
    assert "<td>Dune</td>" in out and "<td>Emma</td>" in out


@pytest.mark.django_db
def test_it_draws_a_header_per_permitted_column(books):
    ds, ada = books
    out = TableComponent().render(TableConfig(), ada, datasource=ds)
    assert "<th>Title</th><th>Region</th>" in out


@pytest.mark.django_db
def test_a_column_the_viewer_may_not_see_is_absent(books):
    """Narrowed in datasources; the component cannot widen it."""
    ds, ada = books
    ada.user_permissions.remove(Permission.objects.get(codename="view_book_title"))
    ada = User.objects.get(pk=ada.pk)
    out = TableComponent().render(TableConfig(), ada, datasource=ds)
    assert "<th>Title</th>" not in out
    assert "Dune" not in out


@pytest.mark.django_db
def test_sort_orders_the_rows(books):
    ds, ada = books
    config = TableConfig(sort=[{"field": "title", "direction": "desc"}])
    out = TableComponent().render(config, ada, datasource=ds)
    assert out.index("Emma") < out.index("Dune")


@pytest.mark.django_db
def test_no_sort_leaves_the_models_ordering(books):
    ds, ada = books
    rows, _ = TableComponent().get_data(TableConfig(), ada, datasource=ds)
    assert rows.query.order_by == ()


@pytest.mark.django_db
def test_a_relation_column_costs_no_query_per_row(books):
    """The count does not grow with the rows. Derivation happens below, so a
    component gets the joins without asking for them."""
    ds, ada = books

    def count_a_render():
        # A fresh user each time: the first render warms the permission cache,
        # which would otherwise make the second look cheaper for the wrong reason.
        viewer = User.objects.get(pk=ada.pk)
        with CaptureQueriesContext(connection) as queries:
            TableComponent().render(TableConfig(), viewer, datasource=ds)
        return len(queries.captured_queries)

    with_two = count_a_render()
    for title in ("Ulysses", "Ariel", "Beloved"):
        Book.objects.create(title=title, owner=ada, region=Region.objects.first())
    assert count_a_render() == with_two


@pytest.mark.django_db
def test_an_uninstalled_format_falls_back_to_html(books):
    """A caller never asks whether contrib.export is installed."""
    ds, ada = books
    out = TableComponent().render(TableConfig(), ada, datasource=ds, format="xlsx")
    assert "<table>" in out

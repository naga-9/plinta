"""The form: which fields it draws, and what it puts in them.

Sending the write is the client's and is covered in the browser suite. What is
here is the half a server decides: whether a field is drawn at all, and what
value and choices it is drawn with.
"""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.components.base import ConfigError, Mode
from plinta.components.form import FormComponent, FormConfig
from plinta.components.registry import get
from plinta.datasources.models import DataSource, DataSourceField
from plinta.permissions.fields import sync_model
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db

EDITABLE = {"title": True, "in_print": True, "region": True}


def grant(user, model, *codenames):
    content_type = ContentType.objects.get_for_model(model)
    for codename in codenames:
        permission, _ = Permission.objects.get_or_create(
            codename=codename, content_type=content_type, defaults={"name": codename}
        )
        user.user_permissions.add(permission)
    return User.objects.get(pk=user.pk)


@pytest.fixture
def source(db):
    datasource = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    for name, label in (
        ("title", "Title"),
        ("in_print", "In print"),
        ("region", "Region"),
    ):
        DataSourceField.objects.create(
            data_source=datasource, field_name=name, label=label, editable=True
        )
    sync_model(Book, EDITABLE)
    return datasource


@pytest.fixture
def writer(db):
    user = User.objects.create_user(username="ada", password="x")  # noqa: S106
    user = grant(
        user,
        Book,
        "view_book",
        "add_book",
        "change_book",
        "view_book_title",
        "view_book_in_print",
        "view_book_region",
        "change_book_title",
        "change_book_in_print",
        "change_book_region",
    )
    return grant(user, Region, "view_region")


@pytest.fixture
def book(db):
    return Book.objects.create(
        title="Ariel", in_print=True, region=Region.objects.create(name="North")
    )


def drawn(config, user, source, record=None):
    return FormComponent().render(
        config, user, datasource=source, record=record, write_url="/w/"
    )


# --- registration -----------------------------------------------------------


def test_it_is_registered():
    assert isinstance(get("form_plinta"), FormComponent)


def test_it_declares_that_it_writes():
    """Core's reference implementation of the write contract, as the table is
    of the read one."""
    assert FormComponent.writes is True


def test_it_is_inline_only():
    """The controls are drawn on the server; there is nothing to fetch."""
    assert FormComponent.mode is Mode.INLINE
    assert FormComponent.supported_modes == frozenset({Mode.INLINE})


def test_a_typo_is_rejected_at_save_time():
    with pytest.raises(ConfigError):
        FormComponent().validate({"submit_labell": "Go"})


# --- which fields it draws --------------------------------------------------


def test_it_draws_the_writable_fields(writer, source, book):
    out = drawn(FormConfig(), writer, source, book)
    for name in ("title", "in_print", "region"):
        assert f'name="{name}"' in out


def test_a_field_the_viewer_may_not_write_is_not_drawn(writer, source, book):
    """A form drawing a field the save would refuse is a promise it cannot
    keep, and the writer only finds out after typing."""
    writer.user_permissions.remove(
        Permission.objects.get(codename="change_book_title")
    )
    stripped = User.objects.get(pk=writer.pk)
    out = drawn(FormConfig(), stripped, source, book)
    assert 'name="title"' not in out
    assert 'name="in_print"' in out


def test_a_field_not_declared_editable_is_not_drawn(writer, source, book):
    DataSourceField.objects.filter(field_name="in_print").update(editable=False)
    sync_model(Book, {**EDITABLE, "in_print": False})
    out = drawn(FormConfig(), User.objects.get(pk=writer.pk), source, book)
    assert 'name="in_print"' not in out


def test_columns_order_and_narrow_what_is_drawn(writer, source, book):
    out = drawn(FormConfig(columns=["region", "title"]), writer, source, book)
    assert out.index('name="region"') < out.index('name="title"')
    assert 'name="in_print"' not in out


def test_a_column_named_but_not_writable_is_still_not_drawn(writer, source, book):
    """`columns` orders and narrows; it does not grant."""
    out = drawn(FormConfig(columns=["title", "owner"]), writer, source, book)
    assert 'name="owner"' not in out


# --- what it puts in them ---------------------------------------------------


def test_a_record_fills_the_controls(writer, source, book):
    out = drawn(FormConfig(), writer, source, book)
    assert 'value="Ariel"' in out
    assert "checked" in out  # in_print is True
    assert f'value="{book.region_id}"' in out


def test_no_record_is_a_create(writer, source):
    """The same form with nothing in it."""
    out = drawn(FormConfig(), writer, source, None)
    assert '"record": null' in out
    assert 'value="Ariel"' not in out


def test_the_payload_is_the_shape_the_client_reads(writer, source, book):
    """`{"config": ...}`, like every other mount.

    Emitted flat, the client finds no config, the adapter sees no record, and
    every save is sent as a create — which is refused for anyone without the
    add permission and looks like a permission bug.
    """
    out = drawn(FormConfig(), writer, source, book)
    assert '{"config": {"record": %d}}' % book.pk in out


def test_a_record_of_another_model_is_not_ours_to_edit(writer, source, book):
    """A detail page about something else. Drawing it filled in would be a
    lie about what saving would change."""
    out = drawn(FormConfig(), writer, source, Region.objects.first())
    assert '"record": null' in out


def test_a_relation_is_drawn_as_the_choices_it_has(writer, source, book):
    Region.objects.create(name="South")
    out = drawn(FormConfig(), writer, source, book)
    assert "<select" in out
    assert ">North</option>" in out
    assert ">South</option>" in out


def test_a_relation_offers_only_choosable_rows(writer, source, book):
    """The same list the write resolves against."""
    Region.objects.create(name="South")
    writer.user_permissions.remove(Permission.objects.get(codename="view_region"))
    out = drawn(FormConfig(), User.objects.get(pk=writer.pk), source, book)
    assert ">South</option>" not in out


def test_the_button_says_what_it_does(writer, source, book):
    out = drawn(FormConfig(submit_label="Update book"), writer, source, book)
    assert "Update book" in out


def test_a_value_is_escaped(writer, source):
    """The record's own data reaches an attribute."""
    nasty = Book.objects.create(title='" onfocus="alert(1)')
    out = drawn(FormConfig(), writer, source, nasty)
    assert 'onfocus="alert(1)"' not in out

"""The write half of a card's conversation, with no component in sight.

Deliberately written before anything is wired to it. The table is the only
component that exists, so if it were the first caller it would be the only
thing the shape was ever proved against — and a shape proved against one
table is a table's shape (§8.11).

So both of these are here, and neither is a table:

    one field   what a kanban card writes when it is dragged
    many fields what a form writes when it is submitted
"""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.blocks.models import Block
from plinta.blocks.submit import submit, submitted, writable
from plinta.blocks.write import WriteDenied
from plinta.datasources.models import DataSource, DataSourceField
from plinta.permissions.fields import sync_model
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db


def grant(user, model, *codenames):
    content_type = ContentType.objects.get_for_model(model)
    for codename in codenames:
        permission, _ = Permission.objects.get_or_create(
            codename=codename, content_type=content_type, defaults={"name": codename}
        )
        user.user_permissions.add(permission)


@pytest.fixture
def writer(db):
    user = User.objects.create_user(username="ada", password="secret")  # noqa: S106
    grant(
        user,
        Book,
        "view_book",
        "add_book",
        "change_book",
        "view_book_title",
        "view_book_in_print",
        "change_book_title",
        "change_book_in_print",
    )
    return user


@pytest.fixture
def source(db):
    datasource = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    DataSourceField.objects.create(
        data_source=datasource, field_name="title", label="Title", editable=True
    )
    DataSourceField.objects.create(
        data_source=datasource, field_name="in_print", label="In print", editable=True
    )
    # Visible, and not open to editing.
    DataSourceField.objects.create(
        data_source=datasource, field_name="region__name", label="Region"
    )
    sync_model(Book, {"title": True, "in_print": True, "region__name": False})
    return datasource


@pytest.fixture
def block(source, writer):
    return Block.objects.create(
        name="books", component_type="table_plinta", data_source=source, owner=writer
    )


@pytest.fixture
def book(writer):
    return Book.objects.create(
        title="Ariel", owner=writer, region=Region.objects.create(name="North")
    )


# --- the two shapes, which are the point ------------------------------------


def test_one_field(block, source, writer, book):
    """A kanban card dragged into another column writes exactly this."""
    out = submit(
        block, writer, datasource=source, record=book.pk, values={"in_print": False}
    )
    book.refresh_from_db()
    assert out["errors"] is None
    assert book.in_print is False


def test_many_fields(block, source, writer, book):
    """A submitted form writes exactly this, through the same call."""
    out = submit(
        block,
        writer,
        datasource=source,
        record=book.pk,
        values={"title": "Crow", "in_print": False},
    )
    book.refresh_from_db()
    assert out["errors"] is None
    assert (book.title, book.in_print) == ("Crow", False)


def test_no_record_creates(block, source, writer):
    out = submit(block, writer, datasource=source, values={"title": "Crow"})
    assert out["errors"] is None
    assert Book.objects.get(pk=out["record"]).title == "Crow"


# --- what comes back --------------------------------------------------------


def test_the_saved_row_comes_back(block, source, writer, book):
    """The widget has to redraw, and a write can change a derived column."""
    out = submit(
        block, writer, datasource=source, record=book.pk, values={"title": "Crow"}
    )
    assert out["record"] == book.pk
    assert out["values"]["title"] == "Crow"


def test_a_column_the_viewer_may_not_see_is_not_returned(block, source, book):
    reader = User.objects.create_user(username="bob", password="secret")  # noqa: S106
    grant(reader, Book, "view_book", "change_book", "view_book_title",
          "change_book_title")
    out = submit(
        block, reader, datasource=source, record=book.pk, values={"title": "Crow"}
    )
    assert "title" in out["values"]
    assert "in_print" not in out["values"]


def test_an_invalid_value_answers_rather_than_raising(block, source, writer, book):
    out = submit(
        block,
        writer,
        datasource=source,
        record=book.pk,
        values={"title": "x" * 500},
    )
    assert out["errors"]["title"]
    assert Book.objects.get(pk=book.pk).title == "Ariel"


# --- the gate this module adds ----------------------------------------------


def test_a_column_not_declared_editable_is_refused(block, source, writer, book):
    """Visible is not writable. The DataSource author decides separately."""
    with pytest.raises(WriteDenied, match="region__name"):
        submit(
            block,
            writer,
            datasource=source,
            record=book.pk,
            values={"region__name": "South"},
        )


def test_a_column_the_datasource_never_exposed_is_refused(
    block, source, writer, book
):
    with pytest.raises(WriteDenied, match="owner"):
        submit(
            block, writer, datasource=source, record=book.pk, values={"owner": 1}
        )


def test_a_refusal_names_every_field(block, source, writer, book):
    """Refused, never dropped: half a write reported as success is worse."""
    with pytest.raises(WriteDenied) as exc:
        submit(
            block,
            writer,
            datasource=source,
            record=book.pk,
            values={"title": "Crow", "owner": 1},
        )
    assert exc.value.denied_fields == ["owner"]
    assert Book.objects.get(pk=book.pk).title == "Ariel"


def test_a_traversal_is_never_writable(source, writer):
    """However it is declared: writing one would mean deciding which row."""
    DataSourceField.objects.filter(field_name="region__name").update(editable=True)
    sync_model(Book, {"title": True, "in_print": True, "region__name": True})
    assert "region__name" not in writable(source, writer)


def test_a_field_without_the_change_permission_is_not_writable(source, book):
    viewer = User.objects.create_user(username="eve", password="secret")  # noqa: S106
    grant(viewer, Book, "view_book", "change_book", "view_book_title")
    assert "title" not in writable(source, viewer)


# --- reaching a row ---------------------------------------------------------


def test_a_row_outside_the_blocks_narrowing_is_refused(
    block, source, writer, book
):
    """A card scoped to one region may not write outside it."""
    with pytest.raises(WriteDenied, match="no such record"):
        submit(
            block,
            writer,
            datasource=source,
            record=book.pk,
            values={"title": "Crow"},
            narrow=lambda rows: rows.none(),
        )


def test_a_row_that_does_not_exist_is_refused(block, source, writer):
    with pytest.raises(WriteDenied, match="no such record"):
        submit(
            block, writer, datasource=source, record=9999, values={"title": "Crow"}
        )


# --- reading the body -------------------------------------------------------


def test_a_body_with_no_record_is_a_create():
    assert submitted({"values": {"title": "Crow"}}) == (None, {"title": "Crow"})
    assert submitted({"record": "", "values": {}}) == (None, {})


def test_a_body_names_its_record():
    assert submitted({"record": "7", "values": {"a": 1}}) == ("7", {"a": 1})


def test_a_body_with_no_values_writes_nothing():
    assert submitted({"record": "7"}) == ("7", {})
    assert submitted({"record": "7", "values": "nonsense"}) == ("7", {})

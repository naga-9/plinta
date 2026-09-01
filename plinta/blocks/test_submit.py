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
    assert out["row"]["title"] == "Crow"
    assert out["row"]["_record"] == book.pk
    # And the unformatted value beside it, because a formatted cell cannot
    # seed the editor that writes it back.
    assert out["row"]["_edit"]["title"] == "Crow"


def test_a_column_the_viewer_may_not_see_is_not_returned(block, source, book):
    reader = User.objects.create_user(username="bob", password="secret")  # noqa: S106
    grant(reader, Book, "view_book", "change_book", "view_book_title",
          "change_book_title")
    out = submit(
        block, reader, datasource=source, record=book.pk, values={"title": "Crow"}
    )
    assert "title" in out["row"]
    assert "in_print" not in out["row"]


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


# --- values that are not text -----------------------------------------------
#
# The table shipped able to edit text and nothing else: every editable column
# got a text box, a boolean answered "'Yes' must be either True or False", and
# a relation raised ValueError out of setattr and returned a 500. These are
# the three.


@pytest.fixture
def with_region(source, writer):
    DataSourceField.objects.create(
        data_source=source, field_name="region", label="Region", editable=True
    )
    sync_model(
        Book, {"title": True, "in_print": True, "region__name": False, "region": True}
    )
    grant(writer, Book, "view_book_region", "change_book_region")
    # A related row nobody may see is not one they may be asked to choose,
    # so the picker's model needs its own view permission.
    grant(writer, Region, "view_region")
    return source


def test_a_relation_is_written_by_pk(block, with_region, writer, book):
    south = Region.objects.create(name="South")
    out = submit(
        block, writer, datasource=with_region, record=book.pk,
        values={"region": south.pk},
    )
    book.refresh_from_db()
    assert out["errors"] is None
    assert book.region == south


def test_a_relation_naming_no_row_is_a_rejection(block, with_region, writer, book):
    out = submit(
        block, with_region and writer, datasource=with_region, record=book.pk,
        values={"region": 9999},
    )
    assert out["errors"]["region"]
    book.refresh_from_db()
    assert book.region.name == "North"


def test_a_relation_given_a_label_is_a_rejection_not_a_crash(
    block, with_region, writer, book
):
    """`setattr` raises ValueError before any validation runs, so without a
    guard a viewer typing into the wrong box gets a 500."""
    out = submit(
        block, writer, datasource=with_region, record=book.pk,
        values={"region": "South"},
    )
    assert out["errors"]["region"]


def test_a_boolean_is_written_as_one(block, source, writer, book):
    out = submit(
        block, writer, datasource=source, record=book.pk, values={"in_print": False}
    )
    assert out["errors"] is None
    # And the raw value comes back, which is what seeds the editor next time —
    # not the "No" the cell displays.
    assert out["row"]["_edit"]["in_print"] is False


def test_a_relations_raw_value_is_its_pk(block, with_region, writer, book):
    out = submit(
        block, writer, datasource=with_region, record=book.pk,
        values={"region": book.region_id},
    )
    assert out["row"]["_edit"]["region"] == book.region_id


def test_a_relation_may_only_be_set_to_a_row_the_viewer_may_see(
    block, with_region, writer, book
):
    """The picker and the write read one list.

    `editor_queryset_filter` narrowed the dropdown and not the save, so a
    viewer who typed a pk assigned a row that was never on offer. Resolving
    through the same queryset is what makes that impossible rather than
    unlikely.
    """
    from django.contrib.auth.models import Permission

    hidden = Region.objects.create(name="Hidden")
    writer.user_permissions.remove(
        Permission.objects.get(
            codename="view_region",
            content_type=ContentType.objects.get_for_model(Region),
        )
    )
    writer = User.objects.get(pk=writer.pk)  # permissions are cached per user

    out = submit(
        block, writer, datasource=with_region, record=book.pk,
        values={"region": hidden.pk},
    )
    assert out["errors"]["region"]
    book.refresh_from_db()
    assert book.region.name == "North"


# --- many-to-many -----------------------------------------------------------
#
# The same write as a foreign key, with the count as the only difference: a
# list of pks rather than one. Which is why it goes through `coerced` and the
# pipeline unchanged and needed no second path.


@pytest.fixture
def with_watchers(source, writer):
    from django.contrib.auth.models import Permission

    DataSourceField.objects.create(
        data_source=source, field_name="watchers", label="Watchers", editable=True
    )
    sync_model(
        Book,
        {"title": True, "in_print": True, "region__name": False, "watchers": True},
    )
    grant(writer, Book, "view_book_watchers", "change_book_watchers")
    permission, _ = Permission.objects.get_or_create(
        codename="view_user",
        content_type=ContentType.objects.get_for_model(User),
        defaults={"name": "view_user"},
    )
    writer.user_permissions.add(permission)
    return source


@pytest.fixture
def watchers(db):
    return [
        User.objects.create_user(username=name, password="x")  # noqa: S106
        for name in ("bob", "cal")
    ]


def test_several_rows_are_written(block, with_watchers, writer, book, watchers):
    fresh = User.objects.get(pk=writer.pk)
    out = submit(
        block, fresh, datasource=with_watchers, record=book.pk,
        values={"watchers": [w.pk for w in watchers]},
    )
    assert out["errors"] is None
    assert sorted(book.watchers.values_list("pk", flat=True)) == sorted(
        w.pk for w in watchers
    )


def test_an_empty_list_clears_them(block, with_watchers, writer, book, watchers):
    fresh = User.objects.get(pk=writer.pk)
    book.watchers.set(watchers)
    out = submit(
        block, fresh, datasource=with_watchers, record=book.pk,
        values={"watchers": []},
    )
    assert out["errors"] is None
    assert book.watchers.count() == 0


def test_all_of_them_must_be_choosable(block, with_watchers, writer, book, watchers):
    """Not merely some.

    Taking the permitted ones and dropping the rest would report a success
    for a write nobody asked for — the same reason a denied field is refused
    rather than dropped.
    """
    fresh = User.objects.get(pk=writer.pk)
    out = submit(
        block, fresh, datasource=with_watchers, record=book.pk,
        values={"watchers": [watchers[0].pk, 9999]},
    )
    assert out["errors"]["watchers"]
    assert book.watchers.count() == 0


def test_a_single_value_where_several_are_wanted_is_a_rejection(
    block, with_watchers, writer, book, watchers
):
    fresh = User.objects.get(pk=writer.pk)
    out = submit(
        block, fresh, datasource=with_watchers, record=book.pk,
        values={"watchers": watchers[0].pk},
    )
    assert out["errors"]["watchers"]


def test_the_raw_value_is_a_list_of_pks(block, with_watchers, writer, book, watchers):
    fresh = User.objects.get(pk=writer.pk)
    out = submit(
        block, fresh, datasource=with_watchers, record=book.pk,
        values={"watchers": [watchers[0].pk]},
    )
    assert out["row"]["_edit"]["watchers"] == [watchers[0].pk]


def test_the_cell_reads_as_a_list_of_names(
    block, with_watchers, writer, book, watchers
):
    """`auth.User.None` is what a manager renders as."""
    fresh = User.objects.get(pk=writer.pk)
    out = submit(
        block, fresh, datasource=with_watchers, record=book.pk,
        values={"watchers": [w.pk for w in watchers]},
    )
    assert out["row"]["watchers"] == "bob, cal"

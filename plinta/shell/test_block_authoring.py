"""The Blocks catalogue and the block inspector (§12.2, §12.3).

The inspector is the screen §12.0 says the admin cannot be: it derives its
form from the component's pydantic schema. The tests below are mostly about
that, and about the one rule the catalogue adds — a block you may not see is
not in it, which is where this differs from the admin.
"""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.blocks.models import Block
from plinta.datasources.models import DataSource, DataSourceField
from plinta.permissions.fields import sync_model
from tests.testapp.models import Book

pytestmark = pytest.mark.django_db


def grant(user, model, *actions):
    ct = ContentType.objects.get_for_model(model)
    for action in actions:
        codename = f"{action}_{model._meta.model_name}"
        perm, _ = Permission.objects.get_or_create(
            codename=codename, content_type=ct, defaults={"name": codename}
        )
        user.user_permissions.add(perm)


@pytest.fixture
def books(db):
    source = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    for name, label in (("title", "Title"), ("in_print", "In print")):
        DataSourceField.objects.create(
            data_source=source, field_name=name, label=label
        )
    sync_model(Book, {"title": False, "in_print": False})
    return source


@pytest.fixture
def author(db, client, books):
    user = User.objects.create_user(username="ada", password="secret")  # noqa: S106
    grant(user, Block, "view", "add", "change", "delete")
    ct = ContentType.objects.get_for_model(Book)
    for codename in ("view_book", "view_book_title", "view_book_in_print"):
        perm, _ = Permission.objects.get_or_create(
            codename=codename, content_type=ct, defaults={"name": codename}
        )
        user.user_permissions.add(perm)
    client.force_login(user)
    return user


@pytest.fixture
def block(db, books, author):
    return Block.objects.create(
        name="book-table",
        component_type="table_plinta",
        data_source=books,
        config={"page_size": 25},
        owner=author,
    )


# --- the catalogue ---------------------------------------------------------


def test_the_catalogue_needs_more_than_read(client, db):
    """`view_block` is what every dashboard needs; it is not authoring."""
    reader = User.objects.create_user(username="bob", password="secret")  # noqa: S106
    grant(reader, Block, "view")
    client.force_login(reader)
    assert client.get("/blocks/").status_code == 404


def test_the_catalogue_lists_only_what_the_viewer_may_see(client, db, books, author):
    mine = Block.objects.create(
        name="mine", component_type="table_plinta", data_source=books, owner=author
    )
    other = User.objects.create_user(username="eve", password="secret")  # noqa: S106
    theirs = Block.objects.create(
        name="theirs", component_type="table_plinta", data_source=books, owner=other
    )
    body = client.get("/blocks/").content.decode()
    assert f"/blocks/{mine.pk}/" in body
    assert f"/blocks/{theirs.pk}/" not in body


def test_creating_a_block_lands_on_its_inspector(client, author, books):
    response = client.post(
        "/blocks/",
        {"name": "sales", "component_type": "table_plinta", "data_source": books.pk},
    )
    created = Block.objects.get(name="sales")
    assert response.headers["Location"] == f"/blocks/{created.pk}/"
    # Owned, not public: publishing is a separate decision.
    assert created.owner == author


def test_duplicating_copies_the_config_under_a_free_name(client, author, block):
    client.post("/blocks/", {"action": "duplicate", "block": block.pk})
    copy = Block.objects.get(name="book-table-copy")
    assert copy.config == block.config
    assert copy.owner == author


def test_a_second_duplicate_does_not_collide(client, author, block):
    client.post("/blocks/", {"action": "duplicate", "block": block.pk})
    client.post("/blocks/", {"action": "duplicate", "block": block.pk})
    assert Block.objects.filter(name="book-table-copy-2").exists()


def test_deleting_removes_it(client, author, block):
    client.post("/blocks/", {"action": "delete", "block": block.pk})
    assert not Block.objects.filter(pk=block.pk).exists()


def test_a_block_the_viewer_cannot_see_cannot_be_deleted(client, db, books):
    other = User.objects.create_user(username="eve", password="secret")  # noqa: S106
    theirs = Block.objects.create(
        name="theirs", component_type="table_plinta", data_source=books, owner=other
    )
    watcher = User.objects.create_user(username="sam", password="secret")  # noqa: S106
    grant(watcher, Block, "view", "change", "delete")
    client.force_login(watcher)
    assert client.post(
        "/blocks/", {"action": "delete", "block": theirs.pk}
    ).status_code == 404
    assert Block.objects.filter(pk=theirs.pk).exists()


# --- the inspector ---------------------------------------------------------


def test_the_inspector_derives_its_controls_from_the_schema(client, author, block):
    from plinta.blocks.inspector import settings_for
    from plinta.components.registry import get

    drawn = {c["name"] for c in settings_for(get("table_plinta"), block, author)}
    assert {"columns", "sort", "page_size"} <= drawn


def test_a_blank_control_means_the_components_default(client, author, block):
    """The inspector's base is the schema, not the block — so nothing is
    inherited from a layer above it."""
    from plinta.blocks.inspector import settings_for
    from plinta.components.registry import get

    drawn = {c["name"]: c for c in settings_for(get("table_plinta"), block, author)}
    page_size = drawn["page_size"]
    assert page_size["value"] == 25          # the block's own
    assert page_size["overridden"] is True
    assert page_size["inherited_value"] == get("table_plinta").config_schema.model_fields["page_size"].default


def test_the_component_cannot_be_changed(client, author, block):
    body = client.get(f"/blocks/{block.pk}/").content.decode()
    assert 'name="component_type"' not in body


def test_saving_settings_stores_them(client, author, block):
    client.post(
        f"/blocks/{block.pk}/",
        {"what": "config", "page_size": "50", "columns": ["title"]},
    )
    block.refresh_from_db()
    assert block.config["page_size"] == 50
    assert block.config["columns"] == ["title"]


def test_a_blank_setting_is_not_stored(client, author, block):
    client.post(
        f"/blocks/{block.pk}/",
        {"what": "config", "page_size": "", "columns": ["title"]},
    )
    block.refresh_from_db()
    assert "page_size" not in block.config


def test_a_bad_setting_reports_rather_than_saves(client, author, block):
    body = client.post(
        f"/blocks/{block.pk}/", {"what": "config", "page_size": "banana"}
    ).content.decode()
    block.refresh_from_db()
    assert block.config["page_size"] == 25
    assert "page_size" in body


def test_publishing_clears_the_owner(client, author, block):
    client.post(
        f"/blocks/{block.pk}/",
        {"what": "block", "name": "book-table", "public": "on",
         "mode": "", "description": "", "icon": "", "queryset_modifier": "",
         "base_filter": "{}", "is_active": "on", "data_source": block.data_source.pk},
    )
    block.refresh_from_db()
    assert block.owner is None


def test_a_reader_cannot_reach_the_inspector(client, db, books):
    """A public block is readable on a page and still not editable here."""
    other = User.objects.create_user(username="eve", password="secret")  # noqa: S106
    public = Block.objects.create(
        name="public", component_type="table_plinta", data_source=books,
        config={"page_size": 25}, owner=None,
    )
    grant(other, Block, "view")
    client.force_login(other)
    response = client.post(
        f"/blocks/{public.pk}/", {"what": "config", "page_size": "99"}
    )
    public.refresh_from_db()
    assert response.status_code == 404
    assert public.config["page_size"] == 25


def test_an_unregistered_component_says_so_rather_than_failing(client, author, books):
    orphan = Block.objects.create(
        name="orphan", component_type="not_installed", data_source=books,
        owner=author,
    )
    body = client.get(f"/blocks/{orphan.pk}/").content.decode()
    assert "not registered" in body

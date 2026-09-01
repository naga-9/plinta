"""The write endpoint: one card, one row, the fields being written.

The mirror of `test_block_data`. Everything about *which* fields may be
written is `blocks.submit`'s and tested there; what is here is the transport —
the content type, the method, the status codes, and the two refusals that are
not the same refusal.
"""
import json

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.blocks.models import Block
from plinta.components.base import Component, ComponentConfig
from plinta.components.registry import register_component
from plinta.datasources.models import DataSource, DataSourceField
from plinta.pages.models import MenuGroup, MenuSection, Page, PageBlock
from plinta.permissions.fields import sync_model
from tests.testapp.models import Book

pytestmark = pytest.mark.django_db

CONFIG_MODELS = (Block, Page)


def grant(user, model, *codenames):
    content_type = ContentType.objects.get_for_model(model)
    for codename in codenames:
        permission, _ = Permission.objects.get_or_create(
            codename=codename, content_type=content_type, defaults={"name": codename}
        )
        user.user_permissions.add(permission)


@pytest.fixture
def writing_component(component_registry):
    """A component that says it writes, so the endpoint has one to reach.

    Registered here rather than using the table, which does not write yet:
    the endpoint's own behaviour should not wait on a component's.
    """

    @register_component("writer", label="Writer")
    class Writer(Component):
        config_schema = ComponentConfig
        writes = True

        def render(self, config, user, **context):
            return "<div></div>"

    @register_component("reader", label="Reader")
    class Reader(Component):
        config_schema = ComponentConfig
        writes = False

        def render(self, config, user, **context):
            return "<div></div>"

    return Writer


@pytest.fixture
def screen(db, client, writing_component):
    ada = User.objects.create_user(username="ada", password="secret")  # noqa: S106
    grant(ada, Book, "view_book", "add_book", "change_book", "view_book_title",
          "change_book_title")
    for model in CONFIG_MODELS:
        grant(ada, model, f"view_{model._meta.model_name}")

    book = Book.objects.create(title="Ariel", owner=ada)
    source = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    DataSourceField.objects.create(
        data_source=source, field_name="title", label="Title", editable=True
    )
    sync_model(Book, {"title": True})

    section = MenuSection.objects.create(name="Reference")
    group = MenuGroup.objects.create(section=section, name="Catalog")
    page = Page.objects.create(
        name="Catalog", slug="catalog", owner=ada, menu_group=group
    )
    block = Block.objects.create(
        name="books", component_type="writer", data_source=source, owner=ada
    )
    placement = PageBlock.objects.create(page=page, block=block, column=0, row=0)
    client.force_login(User.objects.get(pk=ada.pk))
    return page, placement, block, book


def url(page, placement):
    return f"/pages/{page.pk}/blocks/{placement.pk}/write/"


def post(client, page, placement, body):
    return client.post(
        url(page, placement), data=json.dumps(body),
        content_type="application/json",
    )


# --- the happy path ---------------------------------------------------------


def test_a_write_saves_and_answers_with_the_row(client, screen):
    page, placement, _, book = screen
    response = post(client, page, placement,
                    {"record": book.pk, "values": {"title": "Crow"}})
    assert response.status_code == 200
    body = response.json()
    assert body["errors"] is None
    assert body["row"]["title"] == "Crow"
    book.refresh_from_db()
    assert book.title == "Crow"


def test_no_record_creates(client, screen):
    page, placement, _, _ = screen
    response = post(client, page, placement, {"values": {"title": "Crow"}})
    assert response.status_code == 200
    assert Book.objects.get(pk=response.json()["record"]).title == "Crow"


def test_creating_needs_the_add_permission_not_the_change_one(client, screen):
    """A create is authorised as `add`, so a viewer who may edit every row
    still may not make one."""
    page, placement, _, _ = screen
    ada = User.objects.get(username="ada")
    ada.user_permissions.remove(
        Permission.objects.get(
            codename="add_book",
            content_type=ContentType.objects.get_for_model(Book),
        )
    )
    response = post(client, page, placement, {"values": {"title": "Crow"}})
    assert response.status_code == 403
    assert not Book.objects.filter(title="Crow").exists()


# --- the transport ----------------------------------------------------------


def test_a_get_is_refused(client, screen):
    page, placement, _, _ = screen
    assert client.get(url(page, placement)).status_code == 405


def test_another_content_type_is_refused(client, screen):
    """One content type for writes, so there is one thing to parse."""
    page, placement, _, _ = screen
    response = client.post(url(page, placement), data="title=Crow",
                           content_type="application/x-www-form-urlencoded")
    assert response.status_code == 415


def test_an_unreadable_body_is_a_400(client, screen):
    page, placement, _, _ = screen
    response = client.post(url(page, placement), data="{oh dear",
                           content_type="application/json")
    assert response.status_code == 400


def test_a_body_that_is_not_an_object_is_a_400(client, screen):
    page, placement, _, _ = screen
    response = post(client, page, placement, ["title"])
    assert response.status_code == 400


def test_signing_in_is_required(client, screen):
    page, placement, _, book = screen
    client.logout()
    response = post(client, page, placement,
                    {"record": book.pk, "values": {"title": "Crow"}})
    assert response.status_code in (302, 403)
    book.refresh_from_db()
    assert book.title == "Ariel"


# --- the three different noes -----------------------------------------------


def test_a_component_that_does_not_write_is_refused(client, screen):
    """The component's answer, not the viewer's: a chart refuses everyone."""
    page, placement, block, book = screen
    Block.objects.filter(pk=block.pk).update(component_type="reader")
    response = post(client, page, placement,
                    {"record": book.pk, "values": {"title": "Crow"}})
    assert response.status_code == 405
    book.refresh_from_db()
    assert book.title == "Ariel"


def test_a_field_the_viewer_may_not_write_is_a_403(client, screen):
    """A refusal: it will not succeed however the values are changed."""
    page, placement, _, book = screen
    response = post(client, page, placement,
                    {"record": book.pk, "values": {"owner": 1}})
    assert response.status_code == 403
    assert response.json()["fields"] == ["owner"]


def test_an_invalid_value_is_a_422_naming_the_field(client, screen):
    """A rejection: change the value and it will."""
    page, placement, _, book = screen
    response = post(client, page, placement,
                    {"record": book.pk, "values": {"title": "x" * 500}})
    assert response.status_code == 422
    assert response.json()["errors"]["title"]
    book.refresh_from_db()
    assert book.title == "Ariel"


def test_a_block_on_another_page_is_not_reachable(client, screen):
    """The same resolution as the read half, so a write cannot reach a card
    a read could not."""
    page, placement, _, book = screen
    other = Page.objects.create(name="Other", slug="other", owner=page.owner)
    response = client.post(
        f"/pages/{other.pk}/blocks/{placement.pk}/write/",
        data=json.dumps({"record": book.pk, "values": {"title": "Crow"}}),
        content_type="application/json",
    )
    assert response.status_code == 404

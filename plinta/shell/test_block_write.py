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

from plinta.blocks.models import Block, SavedView
from pydantic import Field

from plinta.components.base import ColumnsConfig, Component, ComponentConfig
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

    class WriterConfig(ColumnsConfig):
        page_size: int = Field(default=25, gt=0)
        striped: bool = False

    @register_component("writer", label="Writer")
    class Writer(Component):
        config_schema = WriterConfig
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


# --- the form a card opens --------------------------------------------------


def form_url(page, placement):
    return f"/pages/{page.pk}/blocks/{placement.pk}/form/"


def test_a_record_is_asked_for_by_id(client, screen):
    page, placement, _, book = screen
    response = client.get(form_url(page, placement), {"record": book.pk})
    assert response.status_code == 200
    assert 'value="Ariel"' in response.content.decode()


def test_no_record_is_a_create(client, screen):
    """Which is all that separates "add" from "edit"."""
    page, placement, _, _ = screen
    body = client.get(form_url(page, placement)).content.decode()
    assert '"record": null' in body


def test_a_record_that_does_not_exist_is_not_found(client, screen):
    page, placement, _, _ = screen
    assert client.get(form_url(page, placement), {"record": 9999}).status_code == 404


def test_a_record_named_unusably_is_not_found(client, screen):
    """A pk the key cannot be compared against raises rather than missing."""
    page, placement, _, _ = screen
    assert client.get(form_url(page, placement), {"record": "x"}).status_code == 404


def test_a_form_cannot_be_opened_on_an_unreachable_row(client, screen, settings):
    """The same gate the write applies, so a form cannot be opened on a row
    that could not then be saved."""
    page, placement, _, book = screen
    placement.context_filter = {"title": "Nothing like this"}
    placement.save()
    assert client.get(
        form_url(page, placement), {"record": book.pk}
    ).status_code == 404


def test_signing_in_is_required_to_open_one(client, screen):
    page, placement, _, book = screen
    client.logout()
    response = client.get(form_url(page, placement), {"record": book.pk})
    assert response.status_code in (302, 403)


def test_a_form_on_another_page_is_not_reachable(client, screen):
    """The same resolution as both other halves: a form cannot be opened on a
    card a read could not reach."""
    page, placement, _, book = screen
    other = Page.objects.create(name="Other", slug="other", owner=page.owner)
    assert client.get(
        f"/pages/{other.pk}/blocks/{placement.pk}/form/", {"record": book.pk}
    ).status_code == 404


# --- managing a block's saved views -----------------------------------------


def views_url(page, placement):
    return f"/pages/{page.pk}/blocks/{placement.pk}/views/"


@pytest.fixture
def may_save(screen):
    """The viewer, able to save a view but not to publish one."""
    page, placement, block, book = screen
    ada = User.objects.get(username="ada")
    # Everything the write pipeline asks for when a view is saved: the model
    # permission, and a field permission per field changed. `view_savedview`
    # is separate — without it a viewer cannot see their own views, so there
    # is nothing to edit or delete.
    grant(ada, SavedView, "view_savedview", "add_savedview",
          "change_savedview", "delete_savedview",
          "change_savedview_name", "change_savedview_config")
    return page, placement, block, User.objects.get(pk=ada.pk)


def test_the_editor_draws_the_components_own_fields(client, may_save):
    page, placement, _, _ = may_save
    body = client.get(views_url(page, placement)).content.decode()
    assert 'name="page_size"' in body
    assert 'name="striped"' in body


def test_there_is_no_second_control_for_overriding(client, may_save):
    """A blank control means "same as the block". A checkbox beside it was a
    delta model asking to be operated."""
    page, placement, _, _ = may_save
    body = client.get(views_url(page, placement)).content.decode()
    assert "override_" not in body


def test_saving_stores_only_the_delta(client, may_save):
    page, placement, block, _ = may_save
    Block.objects.filter(pk=block.pk).update(config={"page_size": 25})

    response = client.post(views_url(page, placement), {
        "name": "Mine", "page_size": "10",
    })
    assert response.status_code == 302
    view = SavedView.objects.get()
    # `columns` is stored whatever it holds; this component has no `sort`.
    assert view.config == {"page_size": 10, "columns": []}


def test_a_blank_control_is_not_stored(client, may_save):
    """The whole of "same as the block": empty means absent."""
    page, placement, block, _ = may_save
    Block.objects.filter(pk=block.pk).update(config={"page_size": 25})

    client.post(views_url(page, placement), {"name": "Mine", "page_size": ""})
    assert "page_size" not in SavedView.objects.get().config


def test_a_value_equal_to_the_blocks_is_not_stored_either(client, may_save):
    """Typing what the block already says leaves the view inheriting it, so a
    later change to the block still reaches here."""
    page, placement, block, _ = may_save
    Block.objects.filter(pk=block.pk).update(config={"page_size": 25})

    client.post(views_url(page, placement), {"name": "Mine", "page_size": "25"})
    assert "page_size" not in SavedView.objects.get().config


def test_columns_are_stored_even_when_they_match(client, may_save):
    """A list has no blank, so a view's columns are always its own — which is
    what keeps a column added later out of a view saved before it."""
    page, placement, block, _ = may_save
    Block.objects.filter(pk=block.pk).update(config={"columns": []})

    client.post(views_url(page, placement), {"name": "Mine"})
    assert SavedView.objects.get().config["columns"] == []


def test_saving_returns_to_this_placements_view(client, may_save):
    """This placement's parameter, so the other card keeps its own."""
    page, placement, _, _ = may_save
    response = client.post(views_url(page, placement), {"name": "Mine"})
    view = SavedView.objects.get()
    assert response["Location"].endswith(f"?b{placement.pk}_view={view.pk}")


def test_an_invalid_value_is_answered_not_saved(client, may_save):
    page, placement, _, _ = may_save
    response = client.post(views_url(page, placement), {
        "name": "Mine", "page_size": "0",
    })
    assert response.status_code == 422
    assert not SavedView.objects.exists()


def test_publishing_without_the_permission_is_refused(client, may_save):
    page, placement, _, _ = may_save
    response = client.post(views_url(page, placement), {
        "name": "Everyone's", "public": "on",
    })
    assert response.status_code == 403
    assert not SavedView.objects.exists()


def test_publishing_with_it_is_allowed(client, may_save):
    page, placement, _, ada = may_save
    grant(ada, SavedView, "change_savedview_owner")
    client.force_login(User.objects.get(pk=ada.pk))

    response = client.post(views_url(page, placement), {
        "name": "Everyone's", "public": "on",
    })
    assert response.status_code == 302
    assert SavedView.objects.get().owner is None


def test_a_view_can_be_deleted(client, may_save):
    page, placement, block, ada = may_save
    view = SavedView.objects.create(block=block, name="Mine", owner=ada, config={})
    response = client.post(views_url(page, placement), {
        "view": str(view.pk), "action": "delete",
    })
    assert response.status_code == 302
    assert not SavedView.objects.exists()


def test_someone_elses_view_is_not_deletable(client, may_save):
    page, placement, block, _ = may_save
    other = User.objects.create_user(username="bob", password="x")  # noqa: S106
    view = SavedView.objects.create(block=block, name="Theirs", owner=other, config={})
    assert client.post(views_url(page, placement), {
        "view": str(view.pk), "action": "delete",
    }).status_code == 404
    assert SavedView.objects.filter(pk=view.pk).exists()


def test_the_default_control_needs_its_field_permission(client, may_save):
    """`is_default` is a field, so a field permission gates it — the same
    mechanism as publishing (§6.1b)."""
    page, placement, _, _ = may_save
    body = client.get(views_url(page, placement)).content.decode()
    assert 'name="is_default"' not in body


def test_with_the_permission_it_is_offered_and_says_whose_default(client, may_save):
    """One field, two meanings, decided by who owns the row — so the form
    says which rather than leaving it to be discovered."""
    page, placement, _, ada = may_save
    grant(ada, SavedView, "change_savedview_is_default")
    client.force_login(User.objects.get(pk=ada.pk))

    body = client.get(views_url(page, placement)).content.decode()
    assert 'name="is_default"' in body
    assert "Yours" in body


def test_the_shared_case_is_not_described_to_somebody_who_cannot_publish(
    client, may_save
):
    """There is no shared case for them: the box that would cause it is not
    drawn either."""
    page, placement, _, ada = may_save
    grant(ada, SavedView, "change_savedview_is_default")
    client.force_login(User.objects.get(pk=ada.pk))

    body = client.get(views_url(page, placement)).content.decode()
    assert 'data-plinta-default-scope="shared"' not in body
    assert 'name="public"' not in body


def test_somebody_who_can_publish_is_told_both(client, may_save):
    page, placement, _, ada = may_save
    grant(ada, SavedView, "change_savedview_is_default", "change_savedview_owner")
    client.force_login(User.objects.get(pk=ada.pk))

    body = client.get(views_url(page, placement)).content.decode()
    assert 'data-plinta-default-scope="personal"' in body
    assert 'data-plinta-default-scope="shared"' in body


def test_marking_a_default_without_the_permission_is_refused(client, may_save):
    page, placement, _, _ = may_save
    response = client.post(views_url(page, placement), {
        "name": "Mine", "is_default": "on",
    })
    assert response.status_code == 403
    assert not SavedView.objects.exists()


def test_a_personal_default_is_saved(client, may_save):
    page, placement, _, ada = may_save
    grant(ada, SavedView, "change_savedview_is_default")
    client.force_login(User.objects.get(pk=ada.pk))

    client.post(views_url(page, placement), {"name": "Mine", "is_default": "on"})
    view = SavedView.objects.get()
    assert view.is_default is True
    assert view.owner is not None, "personal, so it is this viewer's default"


def test_a_shared_default_is_everyones(client, may_save):
    page, placement, _, ada = may_save
    grant(ada, SavedView, "change_savedview_is_default", "change_savedview_owner")
    client.force_login(User.objects.get(pk=ada.pk))

    client.post(views_url(page, placement), {
        "name": "Everyone's", "is_default": "on", "public": "on",
    })
    view = SavedView.objects.get()
    assert view.is_default is True
    assert view.owner is None


def test_a_boolean_is_a_select_with_three_states(client, may_save):
    """A checkbox cannot say "same as the block" as well as yes and no."""
    page, placement, block, _ = may_save
    Block.objects.filter(pk=block.pk).update(config={"striped": True})
    body = client.get(views_url(page, placement)).content.decode()

    striped = body.split('data-plinta-setting="striped"')[1].split("</select>")[0]
    assert "<select" in striped
    assert "Same as the block — yes" in striped
    assert ">Yes<" in striped and ">No<" in striped


def test_a_scalar_shows_the_blocks_value_as_its_placeholder(client, may_save):
    """Where the value comes from, said by the control rather than beside
    it — which is what a whole extra checkbox used to be for."""
    page, placement, block, _ = may_save
    Block.objects.filter(pk=block.pk).update(config={"page_size": 25})
    body = client.get(views_url(page, placement)).content.decode()

    size = body.split('data-plinta-setting="page_size"')[1].split("</div>")[0]
    assert 'placeholder="25"' in size


def test_a_registered_layout_is_what_the_editor_draws(
    client, may_save, settings, tmp_path, config_layout_registry
):
    """The registry resolving a template is not the same as the editor
    rendering one. Nothing exercised the second, so a broken `{% include %}`
    would have shown up on a consumer's screen and nowhere else."""
    from plinta.forms.layouts import register_config_layout

    page, placement, block, _ = may_save
    directory = tmp_path / "layouts"
    directory.mkdir()
    (directory / "writer.html").write_text(
        "{% load plinta_form %}<fieldset><legend>Only this</legend>"
        '{% setting "page_size" %}</fieldset>',
        encoding="utf-8",
    )
    settings.TEMPLATES = [{**settings.TEMPLATES[0], "DIRS": [str(directory)]}]

    from plinta.components.registry import get

    register_config_layout(get("writer").config_schema, "writer.html")

    body = client.get(views_url(page, placement)).content.decode()
    assert "<legend>Only this</legend>" in body
    assert 'name="page_size"' in body
    assert 'name="striped"' not in body, "a setting the layout omits"

"""Turning a submitted form back into a delta.

A form posts every field; a delta holds only what somebody meant to change.
Getting that wrong turns a view into a copy one save at a time, which freezes
its block silently — the failure ADR 0004 names.
"""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.blocks.models import Block, SavedView
from plinta.blocks.rendering import effective_config
from plinta.blocks.saved_views import (
    INHERIT,
    column_choices,
    controls,
    delta,
    inherited,
    may_publish,
    save,
)
from plinta.datasources.models import DataSource
from tests.testapp.models import Book

pytestmark = pytest.mark.django_db


@pytest.fixture
def block(db):
    user = User.objects.create_user(username="ada", password="x")  # noqa: S106
    source = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    return Block.objects.create(
        name="books",
        component_type="table_plinta",
        data_source=source,
        owner=user,
        config={"page_size": 25, "striped": False, "columns": []},
    )


@pytest.fixture
def ada(block):
    return User.objects.get(username="ada")


# --- what a delta holds -----------------------------------------------------


def test_a_changed_field_is_stored():
    assert delta({"page_size": 50}, {"page_size": 25}) == {"page_size": 50}


def test_a_field_set_to_what_it_already_was_is_not(block):
    """Setting a control to the value it shows leaves the view inheriting it,
    so a later change to the block still reaches here."""
    assert delta({"page_size": 25}, {"page_size": 25}) == {}


def test_inherit_drops_an_override():
    """The way back. Without it a form can only ever add overrides."""
    assert delta({"page_size": INHERIT}, {"page_size": 25}) == {}


def test_a_field_the_block_never_set_is_stored():
    assert delta({"height": "40rem"}, {}) == {"height": "40rem"}


def test_what_is_inherited_is_what_is_absent():
    assert inherited({"page_size": 50}, {"page_size": 25, "striped": False}) == {
        "striped"
    }


# --- why it matters ---------------------------------------------------------


def test_a_block_change_reaches_a_view_that_did_not_override(block, ada):
    """The whole reason for a delta."""
    view = save(block, ada, name="Mine", values={"striped": True})

    Block.objects.filter(pk=block.pk).update(
        config={**block.config, "page_size": 100}
    )
    block.refresh_from_db()

    assert effective_config(block, ada, view)["page_size"] == 100
    assert effective_config(block, ada, view)["striped"] is True


def test_a_block_change_does_not_reach_a_field_the_view_overrode(block, ada):
    view = save(block, ada, name="Mine", values={"page_size": 10})

    Block.objects.filter(pk=block.pk).update(
        config={**block.config, "page_size": 100}
    )
    block.refresh_from_db()

    assert effective_config(block, ada, view)["page_size"] == 10


def test_a_column_added_later_does_not_appear_in_an_existing_view(block, ada):
    """`columns` is the field a view almost always overrides, so this is the
    normal case rather than the exception: the editor offers the new column as
    an unchecked row instead of adding it."""
    view = save(block, ada, name="Two", values={"columns": ["title", "author"]})

    Block.objects.filter(pk=block.pk).update(
        config={**block.config, "columns": ["title", "author", "region"]}
    )
    block.refresh_from_db()

    assert effective_config(block, ada, view)["columns"] == ["title", "author"]


def test_saving_stores_the_delta_and_not_the_form(block, ada):
    """A form posts every field. Stored whole, the view is a copy."""
    view = save(
        block,
        ada,
        name="Mine",
        values={"page_size": 25, "striped": True, "columns": []},
    )
    assert view.config == {"striped": True}


# --- ownership --------------------------------------------------------------


def test_a_view_is_personal_by_default(block, ada):
    assert save(block, ada, name="Mine", values={}).owner == ada


def test_publishing_needs_the_field_permission(block, ada):
    with pytest.raises(PermissionError):
        save(block, ada, name="Everyone's", values={}, public=True)


def test_publishing_with_it_makes_it_public(block, ada):
    ada.user_permissions.add(
        Permission.objects.get_or_create(
            codename="change_savedview_owner",
            content_type=ContentType.objects.get_for_model(SavedView),
            defaults={"name": "change_savedview_owner"},
        )[0]
    )
    granted = User.objects.get(pk=ada.pk)
    assert may_publish(granted)
    assert save(block, granted, name="Everyone's", values={}, public=True).owner is None


def test_an_existing_view_is_updated_not_duplicated(block, ada):
    view = save(block, ada, name="Mine", values={"striped": True})
    again = save(block, ada, name="Renamed", values={"page_size": 10}, view=view)
    assert again.pk == view.pk
    assert again.name == "Renamed"
    assert again.config == {"page_size": 10}
    assert SavedView.objects.count() == 1


# --- the editor's fields ----------------------------------------------------


def test_the_fields_come_from_the_components_own_schema(block, ada):
    """Nothing in the editor knows what a table is: a consumer's component
    declares a schema and gets an editor for it."""
    from plinta.components.registry import get

    drawn = {c["name"] for c in controls(get("table_plinta"), block, ada, None)}
    assert {"page_size", "striped", "columns", "height"} <= drawn


def test_a_field_says_whether_this_view_overrides_it(block, ada):
    """The difference between a delta and a copy. A control showing 25
    because the block says so must be told from one showing 25 because
    somebody chose it."""
    from plinta.components.registry import get

    view = save(block, ada, name="Mine", values={"page_size": 10})
    drawn = {c["name"]: c for c in controls(get("table_plinta"), block, ada, view)}

    assert drawn["page_size"]["overridden"] is True
    assert drawn["page_size"]["value"] == 10
    assert drawn["page_size"]["inherited_value"] == 25

    assert drawn["striped"]["overridden"] is False
    assert drawn["striped"]["value"] is False


# --- the column chooser -----------------------------------------------------


@pytest.fixture
def columns(block):
    from plinta.datasources.models import DataSourceField
    from plinta.permissions.fields import sync_model

    for order, name in enumerate(("title", "in_print", "region__name")):
        DataSourceField.objects.create(
            data_source=block.data_source, field_name=name, label=name, order=order
        )
    sync_model(Book, {"title": False, "in_print": False, "region__name": False})
    ada = User.objects.get(username="ada")
    for name in ("view_book", "view_book_title", "view_book_in_print",
                 "view_book_region__name"):
        ada.user_permissions.add(
            Permission.objects.get_or_create(
                codename=name,
                content_type=ContentType.objects.get_for_model(Book),
                defaults={"name": name},
            )[0]
        )
    return User.objects.get(pk=ada.pk)


def test_every_permitted_column_is_offered(block, columns):
    assert {c["name"] for c in column_choices(block, columns)} == {
        "title", "in_print", "region__name",
    }


def test_a_column_added_later_is_offered_unchecked(block, columns):
    """The behaviour a delta is for: it does not appear in the view, and it
    is there to select."""
    view = save(block, columns, name="Two", values={"columns": ["title", "in_print"]})

    offered = column_choices(block, columns, view)
    assert [c["name"] for c in offered if c["chosen"]] == ["title", "in_print"]
    assert [c["name"] for c in offered if not c["chosen"]] == ["region__name"]


def test_the_chosen_ones_keep_the_views_order(block, columns):
    """Not the block's. The editor is editing a view."""
    view = save(block, columns, name="Backwards",
                values={"columns": ["in_print", "title"]})
    offered = column_choices(block, columns, view)
    assert [c["name"] for c in offered if c["chosen"]] == ["in_print", "title"]


def test_a_column_the_viewer_may_not_see_is_not_offered(block, columns):
    columns.user_permissions.remove(
        Permission.objects.get(codename="view_book_in_print")
    )
    stripped = User.objects.get(pk=columns.pk)
    assert "in_print" not in {c["name"] for c in column_choices(block, stripped)}

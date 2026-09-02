"""The page composer (§12.4).

Core owns the four integers and the rule that writes them; `contrib.composer`
owns the dragging. So the tests here are about the rule, and about the screen
being complete without any JavaScript at all.
"""
import json

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.blocks.models import Block
from plinta.datasources.models import DataSource, DataSourceField
from plinta.pages.models import Page, PageBlock
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
def author(db, client):
    user = User.objects.create_user(username="ada", password="secret")  # noqa: S106
    grant(user, Page, "view", "add", "change")
    grant(user, PageBlock, "view", "add", "change", "delete")
    grant(user, Block, "view", "add", "change")
    client.force_login(user)
    return user


@pytest.fixture
def sales(db, author):
    source = DataSource.objects.create(
        name="books", label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    DataSourceField.objects.create(
        data_source=source, field_name="title", label="Title"
    )
    sync_model(Book, {"title": False})
    page = Page.objects.create(name="Sales", slug="sales", owner=author)
    block = Block.objects.create(
        name="books", component_type="table_plinta", data_source=source, owner=author
    )
    placement = PageBlock.objects.create(
        page=page, block=block, column=0, row=0, width=6, height=4
    )
    return page, block, placement


# --- the list and the screen ------------------------------------------------


def test_the_list_needs_more_than_read(client, db):
    reader = User.objects.create_user(username="bob", password="secret")  # noqa: S106
    grant(reader, Page, "view")
    client.force_login(reader)
    assert client.get("/pages/").status_code == 404


def test_compose_is_not_read_as_a_record_id(client, author, sales):
    """`pages/<pk>/<record>/` would happily match "compose"."""
    page, _, _ = sales
    assert client.get(f"/pages/{page.pk}/compose/").status_code == 200


def test_placing_a_block_puts_it_below_what_is_there(client, author, sales):
    page, block, placement = sales
    client.post(
        f"/pages/{page.pk}/compose/",
        {"what": "place", "block": block.pk, "title": "", "tab": "",
         "is_visible": "on"},
    )
    added = page.placements.exclude(pk=placement.pk).get()
    # Beneath the existing one, full width: a block landing on top of another
    # is a page somebody has to repair before reading it.
    assert added.row == placement.row + placement.height
    assert (added.column, added.width) == (0, 12)


def test_a_block_the_viewer_cannot_see_is_not_offered(client, db, author, sales):
    from plinta.shell.authoring import PlacementForm

    page, _, _ = sales
    other = User.objects.create_user(username="eve", password="secret")  # noqa: S106
    hidden = Block.objects.create(
        name="hidden", component_type="table_plinta", owner=other
    )
    form = PlacementForm(page=page, user=author)
    assert hidden not in form.fields["block"].queryset


def test_removing_a_placement(client, author, sales):
    page, _, placement = sales
    client.post(
        f"/pages/{page.pk}/compose/",
        {"what": "remove", "placement": placement.pk},
    )
    assert not PageBlock.objects.filter(pk=placement.pk).exists()


def test_the_grid_form_moves_a_block(client, author, sales):
    page, _, placement = sales
    client.post(
        f"/pages/{page.pk}/compose/",
        {
            "what": "positions",
            f"position-{placement.pk}-column": "6",
            f"position-{placement.pk}-row": "2",
            f"position-{placement.pk}-width": "6",
            f"position-{placement.pk}-height": "3",
        },
    )
    placement.refresh_from_db()
    assert (placement.column, placement.row, placement.width, placement.height) == (
        6, 2, 6, 3
    )


# --- the rule the drag posts to --------------------------------------------


def test_a_width_past_the_edge_is_clamped(client, author, sales):
    """A drag that ends slightly past the edge means the edge, not an error."""
    page, _, placement = sales
    client.post(
        f"/pages/{page.pk}/positions/",
        data=json.dumps({str(placement.pk): {"column": 8, "width": 99}}),
        content_type="application/json",
    )
    placement.refresh_from_db()
    assert (placement.column, placement.width) == (8, 4)


def test_an_unreadable_number_moves_nothing_else(client, author, sales):
    """One bad value should not lose the other eleven the same drag carried."""
    page, _, placement = sales
    client.post(
        f"/pages/{page.pk}/positions/",
        data=json.dumps({str(placement.pk): {"column": "banana", "row": 3}}),
        content_type="application/json",
    )
    placement.refresh_from_db()
    assert (placement.column, placement.row) == (0, 3)


def test_a_placement_on_another_page_is_ignored(client, author, sales):
    """The id is a number in a POST body. A client guessing one should not
    learn from the answer whether it exists."""
    page, block, _ = sales
    elsewhere = Page.objects.create(name="Other", slug="other", owner=author)
    theirs = PageBlock.objects.create(page=elsewhere, block=block, column=0, row=0)

    response = client.post(
        f"/pages/{page.pk}/positions/",
        data=json.dumps({str(theirs.pk): {"column": 9}}),
        content_type="application/json",
    )
    theirs.refresh_from_db()
    assert response.status_code == 200
    assert theirs.column == 0


def test_a_viewer_who_cannot_change_the_page_cannot_drag(client, db, sales):
    page, _, placement = sales
    other = User.objects.create_user(username="eve", password="secret")  # noqa: S106
    grant(other, Page, "view")
    grant(other, PageBlock, "change")
    client.force_login(other)

    response = client.post(
        f"/pages/{page.pk}/positions/",
        data=json.dumps({str(placement.pk): {"column": 9}}),
        content_type="application/json",
    )
    placement.refresh_from_db()
    assert response.status_code in {403, 404}
    assert placement.column == 0


def test_unreadable_json_is_refused(client, author, sales):
    page, _, _ = sales
    response = client.post(
        f"/pages/{page.pk}/positions/",
        data="not json",
        content_type="application/json",
    )
    assert response.status_code == 400


def test_moving_touches_nothing_but_the_position(client, author, sales):
    """Moving a card and re-pointing it at another block are different acts."""
    page, block, placement = sales
    placement.title = "Best sellers"
    placement.save()

    client.post(
        f"/pages/{page.pk}/positions/",
        data=json.dumps({str(placement.pk): {"column": 3}}),
        content_type="application/json",
    )
    placement.refresh_from_db()
    assert placement.title == "Best sellers"
    assert placement.block_id == block.pk


# --- the hook the composer hangs on ----------------------------------------


def test_the_page_carries_a_placement_hook(client, author, sales):
    """Core never reads it; it is what lets a composer address one card."""
    page, _, placement = sales
    body = client.get(page.get_absolute_url()).content.decode()
    assert f'data-plinta-placement="{placement.pk}"' in body


def test_a_registered_page_action_is_drawn(client, author, sales, page_action_registry):
    from plinta.pages.actions import register_page_action

    register_page_action("demo", template="testapp/page_action.html")
    page, _, _ = sales
    body = client.get(page.get_absolute_url()).content.decode()
    assert "PAGE-ACTION-PROBE" in body

"""The authoring screens in a real browser (§12.1–12.3).

The saved-view editor draws its settings inside a `<dialog>`; the block
inspector draws the same settings on a plain page. The column chooser and the
sort builder are document-level delegated listeners with no mount step, so
they should work in both — but "should" is exactly what this suite exists to
stop anybody saying, since the bug that prompted it was a mounting one.
"""
import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from plinta.blocks.models import Block
from plinta.datasources.models import DataSource, DataSourceField

pytestmark = pytest.mark.django_db


@pytest.fixture
def authoring(viewer, screen):
    """``viewer`` allowed to reach both authoring screens."""
    for model, actions in (
        (Block, ("add", "change", "delete")),
        (DataSource, ("view", "add", "change")),
        (DataSourceField, ("view", "add", "change", "delete")),
    ):
        content_type = ContentType.objects.get_for_model(model)
        for action in actions:
            codename = f"{action}_{model._meta.model_name}"
            permission, _ = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={"name": codename},
            )
            viewer.user_permissions.add(permission)
    viewer = type(viewer).objects.get(pk=viewer.pk)  # drop the permission cache
    return screen


def test_the_sort_builder_works_outside_a_dialog(
    page, live_server, signed_in, authoring
):
    """The inspector is a plain page, and the builder is a delegated listener.

    The saved-view editor covers the dialog; this covers the other context,
    because "it is the same JavaScript" is a claim and not a check.
    """
    _, block, _ = authoring
    page.goto(f"{live_server.url}/blocks/{block.pk}/")
    page.wait_for_selector("[data-plinta-sort]", timeout=15000)

    assert page.locator(".pl-sort__row").count() == 0
    page.click("[data-plinta-sort-add]")
    assert page.locator(".pl-sort__row").count() == 1
    page.click("[data-plinta-sort-remove]")
    assert page.locator(".pl-sort__row").count() == 0


def test_the_inspector_saves_a_sort_onto_the_block(
    page, live_server, signed_in, authoring
):
    _, block, _ = authoring
    page.goto(f"{live_server.url}/blocks/{block.pk}/")
    page.wait_for_selector("[data-plinta-sort]", timeout=15000)

    page.click("[data-plinta-sort-add]")
    page.select_option('[name="sort_field"]', "title")
    page.select_option('[name="sort_direction"]', "desc")
    page.click('form:has([data-plinta-sort]) button[type="submit"]')
    page.wait_for_url(f"**/blocks/{block.pk}/", timeout=15000)

    block.refresh_from_db()
    assert block.config["sort"] == [{"field": "title", "direction": "desc"}]


def test_the_inspector_shows_the_components_default_as_the_placeholder(
    page, live_server, signed_in, authoring
):
    """Nothing sits above the block, so a blank control falls to the schema."""
    _, block, _ = authoring
    block.config = {}
    block.save()

    page.goto(f"{live_server.url}/blocks/{block.pk}/")
    page.wait_for_selector('[name="page_size"]', timeout=15000)
    control = page.locator('[name="page_size"]')
    assert control.input_value() == ""
    assert control.get_attribute("placeholder")


def test_a_column_can_be_added_to_a_data_source(
    page, live_server, signed_in, authoring
):
    source = DataSource.objects.get(name="books")
    before = source.fields.count()

    page.goto(f"{live_server.url}/data-sources/{source.pk}/")
    page.wait_for_selector('[list="pl-field-paths"]', timeout=15000)

    blank = page.locator('[list="pl-field-paths"]').last
    blank.fill("published_on")
    index = source.fields.count()  # the extra form's index
    page.fill(f'[name="form-{index}-label"]', "Published")
    page.click('form:has([list="pl-field-paths"]) button[type="submit"]')
    page.wait_for_url(f"**/data-sources/{source.pk}/", timeout=15000)

    assert source.fields.count() == before + 1
    assert source.fields.filter(field_name="published_on").exists()


# --- the composer, which is contrib ----------------------------------------


@pytest.fixture
def composing(viewer, screen):
    """``viewer`` allowed to rearrange the page the composer is drawn on."""
    from plinta.pages.models import Page, PageBlock

    for model, actions in ((Page, ("change",)), (PageBlock, ("change",))):
        content_type = ContentType.objects.get_for_model(model)
        for action in actions:
            codename = f"{action}_{model._meta.model_name}"
            permission, _ = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={"name": codename},
            )
            viewer.user_permissions.add(permission)
    return screen


def test_the_layout_is_not_draggable_until_asked(
    page, live_server, signed_in, composing
):
    """The control turns it on. A dashboard nobody is composing must not move
    when somebody drags to select text."""
    subject, _, _ = composing
    page.goto(f"{live_server.url}{subject.get_absolute_url()}")
    page.wait_for_selector("[data-plinta-compose]", timeout=15000)
    assert not page.locator("body.pl-composing").count()

    page.click("[data-plinta-compose]")
    assert page.locator("body.pl-composing").count() == 1


def test_dragging_a_card_moves_it_and_persists(
    page, live_server, signed_in, composing
):
    """The whole point of the app, and the reason it is a browser test: none
    of this is reachable from Python."""
    from plinta.pages.models import PageBlock

    subject, _, placement = composing
    # Half width, because a card already spanning all twelve columns has
    # nowhere to move sideways — which is the clamp working, not a bug.
    placement.width = 6
    placement.save()

    page.goto(f"{live_server.url}{subject.get_absolute_url()}")
    page.wait_for_selector("[data-plinta-compose]", timeout=15000)
    page.click("[data-plinta-compose]")

    card = page.locator("[data-plinta-placement]").first
    box = card.bounding_box()
    grid_box = page.locator(".pl-grid").bounding_box()
    column = grid_box["width"] / 12

    page.mouse.move(box["x"] + 20, box["y"] + 8)
    page.mouse.down()
    page.mouse.move(box["x"] + 20 + column * 3, box["y"] + 8, steps=10)
    page.mouse.up()

    page.wait_for_timeout(500)
    moved = PageBlock.objects.get(pk=placement.pk)
    assert moved.column == 3


def test_the_control_is_absent_without_the_permission(
    page, live_server, signed_in, screen
):
    """`screen`'s viewer may read the page and not rearrange it."""
    subject, _, _ = screen
    page.goto(f"{live_server.url}{subject.get_absolute_url()}")
    page.wait_for_selector(".pl-grid", timeout=15000)
    assert page.locator("[data-plinta-compose]").count() == 0

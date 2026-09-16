"""The authoring screens in a real browser (§12.1–12.3).

The saved-view editor draws its settings inside a dialog; the block inspector
draws the same settings on a plain page. The column chooser and the sort
builder are compilers, so they should work in both — but "should" is exactly
what this suite exists to stop anybody saying, since the bug that prompted it
was a mounting one.
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
    """The inspector is a plain page, and the builder is a compiler.

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


# --- the layout editor ------------------------------------------------------


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


def compose(page, live_server, subject):
    """Open the page and turn the layout editor on, GridStack fetched."""
    page.goto(f"{live_server.url}{subject.get_absolute_url()}")
    page.wait_for_selector("[data-plinta-compose]", timeout=15000)
    assert page.evaluate("() => !window.GridStack"), "fetched on the first click"
    page.click("[data-plinta-compose]")
    page.wait_for_selector(".pl-grid.grid-stack", timeout=15000)


def drag(page, placement_pk, dx, dy):
    """Drag one card by its header, by some columns and rows."""
    card = page.locator(f"[data-plinta-placement='{placement_pk}']")
    header = card.locator(".pl-card__header")
    box = header.bounding_box()
    grid_box = page.locator(".pl-grid").bounding_box()
    column = grid_box["width"] / 12
    row = page.evaluate(
        "() => parseFloat(getComputedStyle(document.documentElement)"
        ".getPropertyValue('--pl-grid-cell')) + parseFloat(getComputedStyle("
        "document.documentElement).getPropertyValue('--pl-grid-gap'))"
    )
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 5, y + 5)
    page.mouse.move(x + column * dx, y + row * dy, steps=12)
    with page.expect_response(lambda r: r.url.endswith("/positions/")):
        page.mouse.up()


def test_the_layout_is_not_draggable_until_asked(
    page, live_server, signed_in, composing
):
    """The control turns it on, and fetches GridStack then rather than for
    every viewer. A dashboard nobody is composing must not move when
    somebody drags to select text."""
    subject, _, _ = composing
    page.goto(f"{live_server.url}{subject.get_absolute_url()}")
    page.wait_for_selector("[data-plinta-compose]", timeout=15000)
    assert not page.locator("body.pl-composing").count()
    assert not page.locator(".pl-grid.grid-stack").count()

    page.click("[data-plinta-compose]")
    page.wait_for_selector("body.pl-composing .pl-grid.grid-stack", timeout=15000)
    assert page.locator("[data-plinta-compose]").inner_text() == "Done"


def test_dragging_a_card_moves_it_and_persists(
    page, live_server, signed_in, composing
):
    """The gesture is GridStack's; where the card ends up is the server's."""
    from plinta.pages.models import PageBlock

    subject, _, placement = composing
    # Half width, because a card already spanning all twelve columns has
    # nowhere to move sideways — which is the clamp working, not a bug.
    placement.width = 6
    placement.save()

    compose(page, live_server, subject)
    drag(page, placement.pk, dx=3, dy=0)

    moved = PageBlock.objects.get(pk=placement.pk)
    assert moved.column == 3


def test_a_card_dropped_on_another_pushes_it_aside(
    page, live_server, signed_in, composing
):
    """Collision handling, which is the bulk of what GridStack is for: the
    card it lands on moves out of the way — two of a size swap places — and
    both moves are one POST."""
    from plinta.pages.models import PageBlock

    subject, block, left = composing
    left.width, left.height = 6, 4
    left.save()
    right = PageBlock.objects.create(
        page=subject, block=block, column=6, row=0, width=6, height=4, title="Twin"
    )

    compose(page, live_server, subject)
    drag(page, right.pk, dx=-6, dy=0)

    left.refresh_from_db()
    right.refresh_from_db()
    assert (right.column, right.row) == (0, 0)
    assert (left.column, left.row) == (6, 0), "swapped, not covered"


def test_done_redraws_the_layout_from_the_server(
    page, live_server, signed_in, composing
):
    """GridStack is used for the gesture and never for the resting layout:
    *Done* hands the grid back to the CSS grid, drawn again from what the
    server stored."""
    subject, _, placement = composing
    placement.width = 6
    placement.save()

    compose(page, live_server, subject)
    drag(page, placement.pk, dx=3, dy=0)
    page.click("[data-plinta-compose]")

    page.wait_for_selector(".pl-grid:not(.grid-stack)", timeout=15000)
    page.wait_for_function(
        f"() => document.querySelector('[data-plinta-placement=\"{placement.pk}\"]')"
        ".style.getPropertyValue('--col').trim() === '3'",
        timeout=15000,
    )
    assert not page.locator("body.pl-composing").count()


def test_the_control_is_absent_without_the_permission(
    page, live_server, signed_in, screen
):
    """`screen`'s viewer may read the page and not rearrange it."""
    subject, _, _ = screen
    page.goto(f"{live_server.url}{subject.get_absolute_url()}")
    page.wait_for_selector(".pl-grid", timeout=15000)
    assert page.locator("[data-plinta-compose]").count() == 0

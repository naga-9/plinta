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

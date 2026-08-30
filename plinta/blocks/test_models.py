"""What a Block refuses to be saved as."""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from plinta.blocks.models import Block
from plinta.datasources.models import DataSource
from tests.testapp.models import Book

pytestmark = pytest.mark.django_db


@pytest.fixture
def ds(db):
    return DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )


def block(ds, component_type="table", **kwargs):
    return Block(
        name="books-table", component_type=component_type, data_source=ds, **kwargs
    )


def test_a_valid_config_passes(ds):
    block(ds, config={"page_size": 25}).full_clean()


def test_an_empty_config_passes(ds):
    block(ds).full_clean()


def test_a_key_the_component_does_not_declare_is_refused(ds):
    """extra='forbid' answers at save time rather than at render time."""
    with pytest.raises(ValidationError) as exc:
        block(ds, config={"page_sise": 25}).full_clean()
    assert "config" in exc.value.error_dict


def test_a_wrong_type_is_refused(ds):
    with pytest.raises(ValidationError):
        block(ds, config={"page_size": "twenty"}).full_clean()


def test_an_uninstalled_component_cannot_judge_its_config(ds):
    """It has no schema to check against, so the config is left as written —
    the same reason it renders an empty slot instead of failing."""
    block(ds, component_type="heatmap", config={"anything": 1}).full_clean()


# --- the mode ---------------------------------------------------------------


def test_inheriting_the_mode_is_always_valid(ds):
    block(ds).full_clean()


def test_a_mode_the_component_supports_is_accepted(ds, component_registry):
    from plinta.components.base import Component
    from plinta.components.registry import register_component

    @register_component("either")
    class Either(Component):
        def render(self, config, user, **context):
            return ""

    block(ds, component_type="either", mode="fetch").full_clean()
    block(ds, component_type="either", mode="inline").full_clean()


def test_a_mode_the_component_cannot_draw_is_refused(ds):
    """table is server-rendered and has no adapter, so a fetch would render
    nothing and say nothing."""
    with pytest.raises(ValidationError) as exc:
        block(ds, mode="fetch").full_clean()
    assert "mode" in exc.value.error_dict


def test_an_uninstalled_component_cannot_judge_the_mode(ds):
    block(ds, component_type="heatmap", mode="fetch").full_clean()

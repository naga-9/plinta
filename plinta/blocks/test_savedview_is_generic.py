"""A saved view works on any component, with no code from that component.

The component below declares a schema unlike the table's and implements
nothing about personalisation. Everything here is the machinery in `blocks`.
"""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.blocks.models import Block, SavedView
from plinta.blocks.rendering import effective_config, render_block, resolve
from plinta.components.base import Component, ComponentConfig, ConfigError, Mode
from plinta.datasources.models import DataSource
from tests.testapp.models import Book

pytestmark = pytest.mark.django_db


class ChartConfig(ComponentConfig):
    """Nothing in common with a table's config beyond the base."""

    series: list[str] = []
    stacked: bool = False
    palette: str = "default"


class ChartComponent(Component):
    label = "Chart"
    config_schema = ChartConfig
    mode = Mode.INLINE

    def render(self, config, user, **context):
        return f"<svg data-palette='{config.palette}'>{','.join(config.series)}</svg>"


@pytest.fixture
def chart_block(db, component_registry):
    component_registry.register_component("chart", label="Chart")(ChartComponent)

    ada = User.objects.create(username="ada")
    Book.objects.create(title="Dune", owner=ada)
    ds = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    for model, codename in ((Block, "view_block"), (SavedView, "view_savedview")):
        perm, _ = Permission.objects.get_or_create(
            codename=codename,
            content_type=ContentType.objects.get_for_model(model),
            defaults={"name": codename},
        )
        ada.user_permissions.add(perm)
    ada = User.objects.get(pk=ada.pk)

    return Block.objects.create(
        name="books-chart",
        component_type="chart",
        data_source=ds,
        owner=ada,
        config={"series": ["pages"], "palette": "default"},
    ), ada


def test_a_delta_over_a_chart_merges(chart_block):
    block, ada = chart_block
    view = SavedView.objects.create(
        block=block, name="mine", owner=ada, config={"palette": "dark"}
    )
    config = effective_config(block, ada, view)
    assert config == {"series": ["pages"], "palette": "dark"}


def test_the_delta_is_validated_by_the_charts_own_schema(chart_block):
    block, ada = chart_block
    view = SavedView.objects.create(
        block=block, name="mine", owner=ada, config={"stacked": True}
    )
    assert resolve(block, ada, view).stacked is True


def test_a_delta_the_chart_rejects_is_refused(chart_block):
    """The component's schema decides, not anything in blocks."""
    block, ada = chart_block
    view = SavedView.objects.create(
        block=block, name="mine", owner=ada, config={"pallete": "dark"}
    )
    with pytest.raises(ConfigError):
        resolve(block, ada, view)


def test_a_default_view_applies_to_a_chart(chart_block):
    block, ada = chart_block
    SavedView.objects.create(
        block=block, name="mine", owner=ada, config={"palette": "dark"}, is_default=True
    )
    assert "dark" in render_block(block, ada)


def test_the_chart_never_sees_the_saved_view(chart_block):
    """It is handed a resolved config and cannot tell one was involved."""
    block, ada = chart_block
    view = SavedView.objects.create(
        block=block, name="mine", owner=ada, config={"series": ["title"]}
    )
    assert render_block(block, ada, view=view) == "<svg data-palette='default'>title</svg>"


def test_the_component_declares_nothing_about_saved_views():
    """Whatever keys a schema declares are deltable, because the merge is a
    dict merge one layer above."""
    assert not any("view" in name for name in dir(ChartComponent))


def test_the_mode_comes_from_the_component_not_the_block(chart_block):
    from plinta.blocks.rendering import mode_of

    block, _ = chart_block
    assert mode_of(block) is Mode.INLINE

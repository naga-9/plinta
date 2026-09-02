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
    column_choices,
    settings_for,
    delta,
    inherited,
    may_publish,
    save,
)
from plinta.datasources.models import DataSource
from tests.testapp.models import Book

pytestmark = pytest.mark.django_db


def grant(user, model, *codenames):
    """One or more permissions on ``model``, and a user with them loaded."""
    content_type = ContentType.objects.get_for_model(model)
    for codename in codenames:
        user.user_permissions.add(
            Permission.objects.get_or_create(
                codename=codename, content_type=content_type,
                defaults={"name": codename},
            )[0]
        )
    return User.objects.get(pk=user.pk)



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


def test_a_blank_control_never_reaches_here():
    """"Same as the block" is a control left empty, which the form omits — so
    there is no sentinel to carry and nothing to operate."""
    assert delta({}, {"page_size": 25}) == {}


def test_a_pinned_field_is_stored_whatever_it_equals():
    """A list has no blank: an empty one is a real answer, so a view's
    columns are always its own."""
    assert delta({"columns": []}, {"columns": []}, {"columns"}) == {"columns": []}


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
    assert view.config == {"striped": True}, "page_size equalled the block's"


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

    drawn = {c["name"] for c in settings_for(get("table_plinta"), block, ada, None)}
    assert {"page_size", "striped", "columns", "height"} <= drawn


def test_a_scalar_carries_its_override_and_the_blocks_value_apart(block, ada):
    """A control showing 25 because the block says 25 must be told from
    one showing 25 because somebody chose it — so the value is the
    override, and the block's is what the control shows behind it."""
    from plinta.components.registry import get

    view = save(block, ada, name="Mine", values={"page_size": 10})
    drawn = {c["name"]: c for c in settings_for(get("table_plinta"), block, ada, view)}

    assert drawn["page_size"]["value"] == 10
    assert drawn["page_size"]["inherited_value"] == 25

    # Not overridden: nothing in the box, the block's value behind it.
    assert drawn["striped"]["value"] is None
    assert drawn["striped"]["inherited_value"] is False


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


# --- a component nobody in core wrote ---------------------------------------
#
# The question this has to answer: a consumer ships a chart, and gets saved
# views without writing a form, an endpoint or a template.


@pytest.fixture
def chart(component_registry, block):
    """A chart-shaped component: no columns to speak of, a closed set, and a
    nested list its author would rather draw themselves."""
    from typing import Literal

    from pydantic import Field as PydanticField

    from plinta.components.base import Component, ComponentConfig
    from plinta.components.registry import register_component

    class ChartConfig(ComponentConfig):
        x_field: str = ""
        chart_type: Literal["line", "bar", "area"] = "line"
        stacked: bool = False
        max_points: int = PydanticField(default=500, gt=0)

    @register_component("chart_probe", label="Chart")
    class Chart(Component):
        config_schema = ChartConfig

        def render(self, config, user, **context):
            return ""

    Block.objects.filter(pk=block.pk).update(
        component_type="chart_probe", config={"chart_type": "bar"}
    )
    block.refresh_from_db()
    return Chart(), block


def test_a_consumers_component_gets_an_editor_for_free(chart, ada):
    component, block = chart
    drawn = {c["name"]: c for c in settings_for(component, block, ada, None)}

    assert drawn["x_field"]["widget"] == "text"
    assert drawn["stacked"]["widget"] == "bool"
    assert drawn["max_points"]["widget"] == "number"


def test_a_closed_set_is_offered_rather_than_typed(chart, ada):
    """A text box would accept every string and validation would refuse all
    but three, so the writer finds the answer by being wrong."""
    component, block = chart
    drawn = {c["name"]: c for c in settings_for(component, block, ada, None)}

    assert drawn["chart_type"]["widget"] == "choice"
    assert drawn["chart_type"]["choices"] == ("line", "bar", "area")
    # The block says "bar" and this view overrides nothing, so the control is
    # empty and offers "same as the block — bar" as its first option.
    assert drawn["chart_type"]["value"] is None
    assert drawn["chart_type"]["inherited_value"] == "bar"


def test_a_component_with_no_columns_is_offered_no_chooser(chart, ada):
    """The chooser follows the *setting*, not the component. A chart has no
    columns to choose between, and a column list on its card was a control
    for something that meant nothing."""
    component, block = chart
    drawn = {c["name"]: c for c in settings_for(component, block, ada, None)}
    assert "columns" not in drawn


def test_a_component_that_does_draw_columns_inherits_the_chooser(block, ada):
    """Registered on `ColumnsConfig`, so it reaches every component that
    declares it has columns — including one written next year."""
    from plinta.components.registry import get

    drawn = {c["name"]: c for c in settings_for(get("table_plinta"), block, ada, None)}
    assert drawn["columns"]["template"] == "plinta/settings/columns.html"


def test_a_delta_over_a_consumers_config_is_still_a_delta(chart, ada):
    component, block = chart
    view = save(block, ada, name="Stacked", values={"stacked": True})
    assert view.config == {"stacked": True}

    Block.objects.filter(pk=block.pk).update(
        config={"chart_type": "area", "max_points": 100}
    )
    block.refresh_from_db()

    from plinta.blocks.rendering import effective_config

    effective = effective_config(block, ada, view)
    assert effective["stacked"] is True       # overridden
    assert effective["chart_type"] == "area"  # inherited, and the block moved


def test_a_column_setting_is_offered_the_blocks_columns(
    block, columns, component_registry
):
    """The bug this closes: a text box took `Me?`, which validated, and the
    aggregate then raised FieldError on everybody's page."""
    from pydantic import Field as PydanticField

    from plinta.components.base import Component, ComponentConfig
    from plinta.components.registry import register_component

    class StatConfig(ComponentConfig):
        total_field: str = PydanticField(
            default="", json_schema_extra={"widget": "column"}
        )

    @register_component("stat_probe", label="Stat")
    class Stat(Component):
        config_schema = StatConfig

        def render(self, config, user, **context):
            return ""

    drawn = {c["name"]: c for c in settings_for(Stat(), block, columns, None)}
    assert drawn["total_field"]["widget"] == "column"
    assert [c["name"] for c in drawn["total_field"]["columns"]] == [
        "title", "in_print", "region__name",
    ]


def test_a_setting_may_admit_only_some_kinds_of_column(block, columns, component_registry):
    """A column that will be **summed** may only be a number. Offered a
    title, `Sum` returns zero rather than failing — worse than an error,
    because nothing says anything is wrong."""
    from pydantic import Field as PydanticField

    from plinta.components.base import Component, ComponentConfig
    from plinta.components.registry import register_component
    from plinta.datasources.models import DataSourceField, Sorter
    from plinta.permissions.fields import sync_model

    DataSourceField.objects.create(
        data_source=block.data_source, field_name="price", label="Price",
        sorter=Sorter.NUMBER, order=9,
    )
    sync_model(Book, {"title": False, "in_print": False, "region__name": False,
                      "price": False})
    viewer = grant(columns, Book, "view_book_price")

    class StatConfig(ComponentConfig):
        total_field: str = PydanticField(
            default="",
            json_schema_extra={"widget": "column", "kinds": ["number"]},
        )

    @register_component("stat_kinds", label="Stat")
    class Stat(Component):
        config_schema = StatConfig

        def render(self, config, user, **context):
            return ""

    drawn = {c["name"]: c for c in settings_for(Stat(), block, viewer, None)}
    offered = [c["name"] for c in drawn["total_field"]["columns"]]
    assert offered == ["price"], "a title cannot be summed"


def test_a_computed_columns_kind_comes_from_its_sorter(block, columns):
    """It resolves to no model field, so the sort hint is the only thing that
    knows — which is the work `sorter` still does there."""
    from plinta.datasources.models import DataSourceField, Sorter

    DataSourceField.objects.create(
        data_source=block.data_source, field_name="line_total", label="Total",
        sorter=Sorter.NUMBER, order=9,
    )
    from plinta.permissions.fields import sync_model

    sync_model(Book, {"title": False, "in_print": False, "region__name": False,
                      "line_total": False})
    viewer = grant(columns, Book, "view_book_line_total")

    offered = {c["name"]: c["kind"] for c in column_choices(block, viewer)}
    assert offered["line_total"] == "number"


def test_a_setting_that_admits_anything_is_offered_everything(block, columns):
    """Any column can carry a link."""
    from plinta.blocks.saved_views import of_kind

    every = column_choices(block, columns)
    assert of_kind(every, ()) == every

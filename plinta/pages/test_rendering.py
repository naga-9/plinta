"""Composing a page: which slots are drawn, and with which filter values."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext

from plinta.blocks.models import Block, SavedView
from plinta.datasources.models import DataSource, DataSourceField
from plinta.pages.models import (
    FilterSet,
    Lookup,
    Page,
    PageBlock,
    PageFilter,
    PageFilterPreference,
)
from plinta.pages.rendering import (
    default_filters,
    filter_kwargs,
    placements_for,
    remember_filters,
    render_page,
    resolve_filters,
    saved_filter_sets,
)
from plinta.permissions.fields import sync_model
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db

MODELS = (Block, SavedView, Page, FilterSet)


@pytest.fixture
def screen(db):
    ada = User.objects.create(username="ada")
    north = Region.objects.create(name="North")
    south = Region.objects.create(name="South")
    Book.objects.create(title="Dune", owner=ada, region=north, in_print=True)
    Book.objects.create(title="Emma", owner=ada, region=south, in_print=False)

    ds = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    DataSourceField.objects.create(data_source=ds, field_name="title", label="Title")
    sync_model(Book, {"title": False})

    ct = ContentType.objects.get_for_model(Book)
    for codename in ("view_book", "view_book_title"):
        perm, _ = Permission.objects.get_or_create(
            codename=codename, content_type=ct, defaults={"name": codename}
        )
        ada.user_permissions.add(perm)
    for model in MODELS:
        codename = f"view_{model._meta.model_name}"
        perm, _ = Permission.objects.get_or_create(
            codename=codename,
            content_type=ContentType.objects.get_for_model(model),
            defaults={"name": codename},
        )
        ada.user_permissions.add(perm)
    ada = User.objects.get(pk=ada.pk)

    block = Block.objects.create(
        name="books-table", component_type="table", data_source=ds, owner=ada
    )
    page = Page.objects.create(name="Catalog", slug="catalog", owner=ada)
    PageBlock.objects.create(page=page, block=block, width=6)
    return page, block, ada


# --- addressing ------------------------------------------------------------


def test_a_page_is_addressed_by_id(screen):
    page, _, _ = screen
    assert page.get_absolute_url() == f"/pages/{page.pk}-catalog/"


def test_two_people_may_use_the_same_slug(screen):
    """The slug is decorative, so nobody negotiates over `my-dashboard`."""
    _, _, ada = screen
    bob = User.objects.create(username="bob")
    Page.objects.create(name="Catalog", slug="catalog", owner=bob)
    assert Page.objects.filter(slug="catalog").count() == 2


def test_a_rename_does_not_change_the_page_a_link_resolves_to(screen):
    page, _, _ = screen
    before = page.pk
    page.slug = "renamed"
    page.save()
    assert page.get_absolute_url() == f"/pages/{before}-renamed/"


# --- composition -----------------------------------------------------------


def test_a_placement_is_drawn(screen):
    page, _, ada = screen
    drawn = render_page(page, ada)
    assert len(drawn) == 1
    assert "Dune" in drawn[0].html


def test_an_invisible_placement_is_not_drawn(screen):
    page, _, ada = screen
    page.placements.update(is_visible=False)
    assert render_page(page, ada) == []


def test_a_block_the_viewer_may_not_see_keeps_its_slot(screen):
    """An empty slot, so the grid keeps its shape."""
    page, block, ada = screen
    bob = User.objects.create(username="bob")
    Page.objects.filter(pk=page.pk).update(owner=None)
    page.refresh_from_db()
    drawn = render_page(page, bob)
    assert len(drawn) == 1
    assert drawn[0].is_empty


def test_a_block_that_fails_says_so_in_its_slot(screen, settings):
    """The other seven still draw. A dashboard must not go dark because one
    block was misconfigured."""
    settings.DEBUG = False
    page, block, ada = screen
    broken = Block.objects.create(
        name="broken",
        component_type="table",
        data_source=block.data_source,
        owner=ada,
        config={"page_sise": 10},
    )
    PageBlock.objects.create(page=page, block=broken, order=1)

    drawn = render_page(page, ada)
    assert "Dune" in drawn[0].html
    assert drawn[1].error
    assert not drawn[1].is_empty


def test_an_uninstalled_component_keeps_its_slot(screen):
    page, block, ada = screen
    block.component_type = "heatmap"
    block.save()
    drawn = render_page(page, ada)
    assert len(drawn) == 1
    assert drawn[0].is_empty


def test_a_placement_may_override_the_title(screen):
    page, _, ada = screen
    page.placements.update(title="Our books")
    assert render_page(page, ada)[0].title == "Our books"


def test_a_placement_without_a_title_uses_the_blocks_name(screen):
    page, _, ada = screen
    assert render_page(page, ada)[0].title == "books-table"


def test_the_grid_position_travels_with_the_placement(screen):
    page, _, ada = screen
    page.placements.update(column=6, row=2, width=6, height=3)
    drawn = render_page(page, ada)[0]
    assert (drawn.column, drawn.row, drawn.width, drawn.height) == (6, 2, 6, 3)


def test_a_row_is_stored_rather_than_derived(screen):
    """A block stays where it was dropped, so nothing pulls it up to fill a
    gap and a row cannot be inferred from the order."""
    page, block, ada = screen
    page.placements.update(row=3)
    PageBlock.objects.create(page=page, block=block, row=0, order=1)
    assert [p.row for p in render_page(page, ada)] == [3, 0]


def test_a_tab_selects_its_placements(screen):
    page, block, ada = screen
    PageBlock.objects.create(page=page, block=block, tab="second", order=1)
    assert len(placements_for(page, ada)) == 2
    assert len(placements_for(page, ada, tab="second")) == 2
    assert len(placements_for(page, ada, tab="other")) == 1


def test_a_placement_with_no_tab_shows_on_every_tab(screen):
    page, _, ada = screen
    assert len(placements_for(page, ada, tab="anything")) == 1


# --- the filter bar --------------------------------------------------------


def test_a_declared_filter_becomes_a_lookup(screen):
    page, _, ada = screen
    PageFilter.objects.create(page=page, field_name="region__name", label="Region")
    assert filter_kwargs(page, {"region__name": "North"}, ada) == {
        "region__name": "North"
    }


def test_a_lookup_shapes_the_keyword(screen):
    page, _, ada = screen
    PageFilter.objects.create(
        page=page, field_name="region__name", label="Region", lookup=Lookup.IN
    )
    assert filter_kwargs(page, {"region__name": ["North"]}, ada) == {
        "region__name__in": ["North"]
    }


def test_a_value_for_an_undeclared_field_is_ignored(screen):
    """The bar is what the page exposes; a query string is not."""
    page, _, ada = screen
    assert filter_kwargs(page, {"in_print": True}, ada) == {}


def test_an_empty_value_is_not_a_filter(screen):
    page, _, ada = screen
    PageFilter.objects.create(page=page, field_name="region__name", label="Region")
    assert filter_kwargs(page, {"region__name": ""}, ada) == {}
    assert filter_kwargs(page, {"region__name": []}, ada) == {}


def test_a_placeholder_resolves_at_query_time(screen, placeholder_registry):
    page, _, ada = screen
    placeholder_registry.register_placeholder("me", lambda ctx: ctx.user.pk)
    assert resolve_filters({"owner": "__ME__"}, ada) == {"owner": ada.pk}


def test_a_filter_reaches_the_blocks(screen):
    page, _, ada = screen
    PageFilter.objects.create(page=page, field_name="region__name", label="Region")
    drawn = render_page(page, ada, filters={"region__name": "North"})
    assert "Dune" in drawn[0].html
    assert "Emma" not in drawn[0].html


def test_a_context_filter_narrows_one_placement_only(screen):
    page, block, ada = screen
    PageBlock.objects.create(
        page=page, block=block, order=1, context_filter={"in_print": False}
    )
    drawn = render_page(page, ada)
    assert "Dune" in drawn[0].html
    assert "Dune" not in drawn[1].html
    assert "Emma" in drawn[1].html


# --- which values apply ----------------------------------------------------


def test_a_filters_own_default_applies(screen):
    page, _, ada = screen
    PageFilter.objects.create(
        page=page, field_name="region__name", label="Region", default_value="North"
    )
    assert default_filters(page, ada) == {"region__name": "North"}


def test_a_default_filter_set_beats_the_controls_default(screen):
    page, _, ada = screen
    PageFilter.objects.create(
        page=page, field_name="region__name", label="Region", default_value="North"
    )
    FilterSet.objects.create(
        page=page,
        name="mine",
        owner=ada,
        values={"region__name": "South"},
        is_default=True,
    )
    assert default_filters(page, ada) == {"region__name": "South"}


def test_a_public_default_set_applies_when_the_viewer_has_none(screen):
    page, _, ada = screen
    FilterSet.objects.create(
        page=page,
        name="shared",
        owner=None,
        values={"region__name": "South"},
        is_default=True,
    )
    assert default_filters(page, ada) == {"region__name": "South"}


def test_the_viewers_own_default_beats_the_public_one(screen):
    page, _, ada = screen
    FilterSet.objects.create(
        page=page, name="shared", owner=None, values={"x": 1}, is_default=True
    )
    FilterSet.objects.create(
        page=page, name="mine", owner=ada, values={"x": 2}, is_default=True
    )
    assert default_filters(page, ada) == {"x": 2}


def test_remembered_state_beats_every_default(screen):
    """What they last had set is what they expect on returning."""
    page, _, ada = screen
    FilterSet.objects.create(
        page=page, name="mine", owner=ada, values={"x": 1}, is_default=True
    )
    remember_filters(page, ada, {"x": 3})
    assert default_filters(page, ada) == {"x": 3}


def test_remembering_overwrites_rather_than_accumulating(screen):
    page, _, ada = screen
    remember_filters(page, ada, {"x": 1})
    remember_filters(page, ada, {"x": 2})
    assert PageFilterPreference.objects.filter(page=page, owner=ada).count() == 1
    assert default_filters(page, ada) == {"x": 2}


def test_a_placeholder_is_remembered_as_written(screen, placeholder_registry):
    """So a saved __CURRENT_QUARTER__ keeps meaning the current quarter."""
    page, _, ada = screen
    remember_filters(page, ada, {"due": "__CURRENT_QUARTER__"})
    assert default_filters(page, ada) == {"due": "__CURRENT_QUARTER__"}


def test_an_anonymous_viewer_remembers_nothing(screen):
    page, _, _ = screen
    remember_filters(page, None, {"x": 1})
    assert not PageFilterPreference.objects.exists()


def test_explicit_filters_beat_every_default(screen):
    page, _, ada = screen
    PageFilter.objects.create(
        page=page, field_name="region__name", label="Region", default_value="North"
    )
    drawn = render_page(page, ada, filters={"region__name": "South"})
    assert "Emma" in drawn[0].html


def test_a_viewer_sees_the_sets_they_may_choose_from(screen):
    page, _, ada = screen
    bob = User.objects.create(username="bob")
    FilterSet.objects.create(page=page, name="mine", owner=ada, values={})
    FilterSet.objects.create(page=page, name="shared", owner=None, values={})
    FilterSet.objects.create(page=page, name="bob's", owner=bob, values={})
    assert [s.name for s in saved_filter_sets(page, ada)] == ["mine", "shared"]


# --- what a page of blocks costs -------------------------------------------


@pytest.mark.django_db
def test_each_extra_block_costs_a_constant(screen):
    """A page's queries grow with the blocks on it and not faster. The page's
    own reads — the menu, the filter controls, the permission cache — are paid
    once however many blocks there are."""
    page, block, ada = screen

    def count_with(n):
        page.placements.all().delete()
        for i in range(n):
            PageBlock.objects.create(page=page, block=block, order=i)
        # Warm the content-type cache first: its miss is paid once per process,
        # not once per render, so counting it would misattribute a fixed cost.
        render_page(page, User.objects.get(pk=ada.pk))
        with CaptureQueriesContext(connection) as q:
            render_page(page, User.objects.get(pk=ada.pk))
        return len(q.captured_queries)

    one, two, four = count_with(1), count_with(2), count_with(4)
    per_block = two - one
    assert four == one + 3 * per_block, "a page of blocks must stay linear"
    assert per_block <= 4, f"{per_block} queries per block is too many"


@pytest.mark.django_db
def test_more_rows_do_not_cost_more_queries(screen):
    """The table draws one page, so a large model is the same page as a small
    one — which is why an inline table does not need to be fetched."""
    page, _, ada = screen

    def count():
        render_page(page, User.objects.get(pk=ada.pk))
        with CaptureQueriesContext(connection) as q:
            render_page(page, User.objects.get(pk=ada.pk))
        return len(q.captured_queries)

    small = count()
    for i in range(100):
        Book.objects.create(title=f"Book {i}", owner=ada)
    assert count() == small

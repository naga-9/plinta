"""Composing a page: which slots are drawn, and with which filter values."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.models import Q
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
    drawn_controls,
    filter_q,
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
        name="books-table", component_type="table_plinta", data_source=ds, owner=ada
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
        component_type="table_plinta",
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
    assert filter_q(page, {"region__name": "North"}, ada) == Q(
        **{"region__name": "North"}
    )


def test_a_lookup_shapes_the_keyword(screen):
    page, _, ada = screen
    PageFilter.objects.create(
        page=page, field_name="region__name", label="Region", lookup=Lookup.IN
    )
    assert filter_q(page, {"region__name": ["North"]}, ada) == Q(**{
        "region__name__in": ["North"]
    })


def test_a_value_for_an_undeclared_field_is_ignored(screen):
    """The bar is what the page exposes; a query string is not."""
    page, _, ada = screen
    assert filter_q(page, {"in_print": True}, ada) == Q()


def test_an_empty_value_is_not_a_filter(screen):
    page, _, ada = screen
    PageFilter.objects.create(page=page, field_name="region__name", label="Region")
    assert filter_q(page, {"region__name": ""}, ada) == Q()
    assert filter_q(page, {"region__name": []}, ada) == Q()


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


# --- boolean controls -------------------------------------------------------


@pytest.fixture
def viewer(db):
    return User.objects.create(username="viewer")


@pytest.fixture
def boolean_page(db):
    """A page with one yes/no control over `Widget.BOOLEAN`."""
    from plinta.pages.models import Page, PageFilter, Widget

    page = Page.objects.create(name="Books", slug="books")
    PageFilter.objects.create(
        page=page, field_name="in_print", label="In print", widget=Widget.BOOLEAN
    )
    return page


@pytest.mark.parametrize(
    "sent,expected",
    [
        ("true", True), ("True", True), ("1", True), ("yes", True), ("on", True),
        ("false", False), ("False", False), ("0", False), ("no", False),
        (True, True), (False, False),
    ],
)
def test_a_yes_no_control_reaches_the_orm_as_a_bool(
    boolean_page, viewer, sent, expected
):
    """The bar draws `true`, and a BooleanField refuses it.

    Django accepts "True" and "1" but not "true", so without coercion the
    query raises ValidationError from inside the ORM.
    """
    assert filter_q(boolean_page, {"in_print": sent}, viewer) == Q(in_print=expected)


def test_false_is_a_filter_not_an_absence(boolean_page, viewer):
    """`No` must narrow. Dropping it would show in-print titles too."""
    assert filter_q(boolean_page, {"in_print": "false"}, viewer) == Q(in_print=False)


def test_any_sends_nothing(boolean_page, viewer):
    """The empty option is 'no opinion', not 'false'."""
    assert filter_q(boolean_page, {"in_print": ""}, viewer) == Q()


def test_a_nonsense_value_is_ignored_rather_than_raising(boolean_page, viewer):
    """It can only come from a hand-edited URL, and a 500 there is worse."""
    assert filter_q(boolean_page, {"in_print": "maybe"}, viewer) == Q()


# --- date ranges, absolute and relative -------------------------------------


@pytest.fixture
def dated(screen):
    """The catalogue page with both date controls over `published_on`."""
    page, _, ada = screen
    PageFilter.objects.create(
        page=page, field_name="published_on", label="Published",
        widget="daterange_plinta",
    )
    return page, ada


def test_a_range_becomes_two_bounds(dated):
    """One control, two keys — the shape a `{field: value}` dict cannot hold."""
    page, ada = dated
    assert filter_q(page, {"published_on": {"from": "2026-01-01",
                                            "to": "2026-12-31"}}, ada) == Q(
        published_on__gte="2026-01-01", published_on__lte="2026-12-31"
    )


def test_half_a_range_is_still_a_filter(dated):
    """"Anything after March" is a question people ask."""
    page, ada = dated
    assert filter_q(page, {"published_on": {"from": "2026-03-01"}}, ada) == Q(
        published_on__gte="2026-03-01"
    )
    assert filter_q(page, {"published_on": {"to": "2026-03-01"}}, ada) == Q(
        published_on__lte="2026-03-01"
    )


def test_an_empty_range_is_no_filter(dated):
    page, ada = dated
    assert filter_q(page, {"published_on": {}}, ada) == Q()


def test_a_range_ignores_the_controls_lookup(dated):
    """A range *is* its lookup; `exact` on a bound would be nonsense."""
    page, ada = dated
    page.filters.update(lookup=Lookup.IN)
    assert filter_q(page, {"published_on": {"from": "2026-01-01"}}, ada) == Q(
        published_on__gte="2026-01-01"
    )


def test_relative_ranges_or_together(screen):
    """Several names is one choice and several conditions — the other reason a
    filter is a `Q` rather than keyword arguments."""
    from plinta.dates.ranges import resolve_q

    page, _, ada = screen
    PageFilter.objects.create(
        page=page, field_name="published_on", label="When",
        widget="relative_date_plinta",
    )
    built = filter_q(page, {"published_on": ["past", "current_month"]}, ada)
    assert built == Q() & resolve_q("published_on", ["past", "current_month"])


def test_an_unregistered_range_name_is_ignored(screen):
    """It means "no date filter", never "match nothing" — a stored name whose
    package was uninstalled must not empty the screen."""
    page, _, ada = screen
    PageFilter.objects.create(
        page=page, field_name="published_on", label="When",
        widget="relative_date_plinta",
    )
    assert filter_q(page, {"published_on": ["fiscal_year"]}, ada) == Q()


def test_the_relative_control_offers_registered_ranges(screen):
    """Not values from the data: no row contains "current month"."""
    page, _, ada = screen
    PageFilter.objects.create(
        page=page, field_name="published_on", label="When",
        widget="relative_date_plinta",
    )
    drawn = next(d for d in drawn_controls(page, {}, ada)
                 if d.control.field_name == "published_on")
    assert ("current_month", "Current Month") in drawn.options


# --- a viewer-chosen operator ------------------------------------------------


@pytest.fixture
def pickable(screen):
    """A title filter offering three operators."""
    page, _, ada = screen
    control = PageFilter.objects.create(
        page=page, field_name="title", label="Title", lookup=Lookup.ICONTAINS,
        allowed_lookups=["icontains", "exact", "istartswith"],
    )
    return page, control, ada


def test_the_viewer_may_choose_from_what_is_offered(pickable):
    page, _, ada = pickable
    assert filter_q(page, {"title": {"op": "istartswith", "value": "du"}}, ada) == Q(
        title__istartswith="du"
    )


def test_an_operator_not_offered_falls_back_to_the_authors(pickable):
    """The second gate. A query string may *select from* a list; it may never
    *supply* an operator. v1 allowed a path to be assembled from input, so a
    filter on `author` accepted `author__user__password__startswith`."""
    page, _, ada = pickable
    assert filter_q(page, {"title": {"op": "regex", "value": ".*"}}, ada) == Q(
        title__icontains=".*"
    )


def test_a_control_offering_none_ignores_a_submitted_operator(screen):
    """Not opt-out: a filter with no picker cannot be given one by asking."""
    page, _, ada = screen
    PageFilter.objects.create(
        page=page, field_name="title", label="Title", lookup=Lookup.EXACT
    )
    assert filter_q(page, {"title": {"op": "istartswith", "value": "du"}}, ada) == Q(
        title="du"
    )


def test_a_stored_operator_plinta_does_not_know_is_refused(screen):
    """The first gate, at save time. Configuration and a query string are
    different inputs from different people, so both are checked."""
    from django.core.exceptions import ValidationError

    page, _, _ = screen
    control = PageFilter(
        page=page, field_name="title", label="Title", allowed_lookups=["regex"]
    )
    with pytest.raises(ValidationError, match="not lookups plinta knows: regex"):
        control.full_clean()


def test_the_picker_offers_words_not_orm_spellings(pickable):
    """A viewer chooses "starts with", not `istartswith`."""
    page, control, ada = pickable
    assert control.offered_lookups() == [
        ("icontains", "contains"), ("exact", "is"), ("istartswith", "starts with")
    ]


def test_no_allowed_lookups_means_no_picker(screen):
    """Every existing filter is unchanged and grows no control."""
    page, _, ada = screen
    PageFilter.objects.create(page=page, field_name="title", label="Title")
    drawn = next(d for d in drawn_controls(page, {}, ada))
    assert drawn.lookups == []

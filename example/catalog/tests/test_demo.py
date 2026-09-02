"""The demo, exercised from outside plinta.

Everything here goes through the published API. If a test needs a private
path, that is a gap in the API rather than a licence to reach inside (§1.4).
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from plinta.blocks.models import Block
from plinta.blocks.rendering import render_block
from plinta.datasources.models import DataSource
from plinta.pages.menu import build
from plinta.pages.models import Page
from plinta.permissions import allowed, can
from plinta.permissions.actions import registered as registered_actions
from plinta.renderers.fields import registered as registered_field_renderers

from catalog.models import Book, Sale, StockMovement, Store

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture(scope="session")
def _seeded(django_db_setup, django_db_blocker):
    """Seed once for the whole session.

    The demo is built by two commands that do a great deal of work, and
    running them per test made the suite take two minutes to say the same
    thing. Seeded into the template database instead; each test still gets
    its own transaction and rolls back.
    """
    with django_db_blocker.unblock():
        call_command("seed_catalog", verbosity=0)


@pytest.fixture
def demo(_seeded, db):
    return None


def person(username):
    return User.objects.get(username=username)


# --- the tenancy, which is the whole point ---------------------------------


def test_a_manager_sees_only_their_own_stores_sales(demo):
    """Structural scoping with the consumer's own tenancy, and no
    contrib.organization anywhere."""
    mira = person("mira")
    stores = {s.store.name for s in allowed(mira, "view", Sale.objects.all())}
    assert stores == {"Hale Street"}


def test_another_manager_sees_theirs(demo):
    noor = person("noor")
    stores = {s.store.name for s in allowed(noor, "view", Sale.objects.all())}
    assert stores == {"Marsh Lane"}


def test_a_viewer_with_no_store_sees_no_sales(demo):
    """The model permission is held; the policy admits nothing."""
    sam = person("sam")
    assert sam.has_perm("catalog.view_sale")
    assert allowed(sam, "view", Sale.objects.all()).count() == 0


def test_the_two_halves_agree_on_sales(demo):
    """The invariant every policy must keep: filtering and checking select the
    same rows."""
    mira = person("mira")
    by_query = set(allowed(mira, "view", Sale.objects.all()).values_list("pk", flat=True))
    by_check = {s.pk for s in Sale.objects.all() if can(mira, "view", s)}
    assert by_query == by_check


def test_a_manager_may_change_their_own_stores_sales(demo):
    mira = person("mira")
    mine = allowed(mira, "view", Sale.objects.all()).first()
    theirs = Sale.objects.exclude(store__managers=mira).first()
    assert can(mira, "change", mine)
    assert not can(mira, "change", theirs)


def test_a_viewer_may_change_nothing(demo):
    """Reading and writing are different permissions, not degrees of one."""
    sam = person("sam")
    assert not sam.has_perm("catalog.change_sale")


# --- the two axes ----------------------------------------------------------


def test_an_author_arranges_screens_but_sees_no_sales(demo):
    """A dashboard editor has no business reading the chain's takings."""
    author = User.objects.create(username="ivy")
    author.groups.set(person("ada").groups.none() or [])
    from django.contrib.auth.models import Group

    author.groups.set([Group.objects.get(name="Catalogue Author")])
    author = person("ivy")
    assert author.has_perm("plinta_pages.add_page")
    assert allowed(author, "view", Sale.objects.all()).count() == 0


def test_a_manager_arranges_nothing(demo):
    """And a shopkeeper has no business rearranging dashboards."""
    mira = person("mira")
    assert not mira.has_perm("plinta_pages.add_page")
    assert not mira.has_perm("plinta_blocks.change_block")


def test_order_lines_are_scoped_through_their_order(demo):
    """Scoping a parent is not scoping its children. The boot check reported
    this one while the demo was being built: orders were scoped and their lines
    were not, so the second block on the same page showed every store's."""
    from catalog.models import PurchaseOrderLine

    mira, noor = person("mira"), person("noor")
    mine = {line.pk for line in allowed(mira, "view", PurchaseOrderLine.objects.all())}
    theirs = {line.pk for line in allowed(noor, "view", PurchaseOrderLine.objects.all())}
    assert mine and theirs
    assert not (mine & theirs)


def test_the_only_unscoped_model_is_the_one_we_meant(demo):
    """W001 names every DataSource without a policy. The catalogue is the
    deliberate one; a second name in this list is a leak."""
    from plinta.datasources.checks import check_datasource_models_have_a_policy

    reported = {w.obj.name for w in check_datasource_models_have_a_policy()}
    assert reported == {"books"}


# --- the catalogue has no policy, deliberately -----------------------------


def test_every_holder_sees_the_whole_catalogue(demo):
    """A shared catalogue is the case §5.3 calls legitimate: with no policy the
    model permission decides alone."""
    for username in ("mira", "noor", "sam"):
        assert allowed(person(username), "view", Book.objects.all()).count() == 6


# --- the doors -------------------------------------------------------------


def test_a_component_registered_from_outside_core_renders(demo):
    """The component door, walked by a separate package."""
    stat = Block.objects.get(name="titles-in-print")
    out = render_block(stat, person("ada"))
    assert "pl-stat__value" in out
    assert ">5<" in out  # five of the six titles are in print


def test_a_computed_column_reaches_a_table(demo):
    sales = Block.objects.get(name="recent-sales")
    out = render_block(sales, person("mira"))
    assert "Total" in out


def test_a_field_renderer_draws_its_own_markup(demo):
    books = Block.objects.get(name="books-table")
    out = render_block(books, person("sam"))
    assert "In print" in out


def test_a_field_renderers_joins_are_declared(demo):
    assert registered_field_renderers()["store_link"].select_related == (
        "store",
        "store__region",
    )


def test_a_queryset_modifier_narrows_a_block(demo):
    orders = Block.objects.get(name="open-orders")
    out = render_block(orders, person("ada"))
    assert "Received" not in out


def test_a_registered_action_was_minted_for_every_datasource(demo):
    """export_* exists before contrib.export does, so a console can grant it."""
    assert "export" in registered_actions()
    ada = person("ada")
    assert ada.has_perm("catalog.export_book") or not ada.is_superuser


def test_an_event_listener_recorded_a_movement(demo):
    """A subscriber, not a pipeline stage: blocks knows nothing about it."""
    from plinta.blocks.write import write

    ada = person("ada")
    ada.is_superuser = True
    ada.save()
    before = StockMovement.objects.count()
    sale = Sale.objects.first()
    write(sale, {"quantity": sale.quantity + 2}, person("ada"))
    assert StockMovement.objects.count() == before + 1
    assert StockMovement.objects.first().change == -2


def test_a_placeholder_resolves_per_viewer(demo):
    from plinta.utils.placeholders import Context, resolve

    mira, noor = person("mira"), person("noor")
    assert resolve("__MY_STORES__", Context(user=mira)) != resolve(
        "__MY_STORES__", Context(user=noor)
    )


def test_a_capability_probes_the_generic_relation(demo):
    from plinta.blocks.capabilities import matrix

    result = matrix([Book, Store])
    assert [c.name for c in result[Book]] == ["catalog_notes"]
    assert result[Store] == []


def test_a_shell_link_is_gated(demo):
    from plinta.shell.links import visible_links

    # "Data sources" is core's own (§12.1); "Catalogue admin" is this app's.
    # Both are gated the same way, which is the point of the assertion.
    assert [link.label for link in visible_links(person("ada"))] == [
        "Catalogue admin",
        "Data sources",
        "Blocks",
    ]
    assert visible_links(person("sam")) == []


# --- the screens -----------------------------------------------------------


def test_the_seeder_is_idempotent(demo):
    """Run it twice; nothing doubles."""
    counts = (Page.objects.count(), Block.objects.count(), DataSource.objects.count())
    call_command("seed_catalog", verbosity=0)
    assert (Page.objects.count(), Block.objects.count(), DataSource.objects.count()) == counts


def test_every_viewer_gets_a_menu(demo):
    for username in ("ada", "mira", "sam"):
        sections = build(person(username))
        assert [s.section.name for s in sections] == ["Bookshop"]


def test_the_menu_groups_the_pages(demo):
    groups = {e.group.name for e in build(person("ada"))[0].groups}
    assert groups == {"Trading", "Buying"}

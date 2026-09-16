"""The whole menu: pages and links in one structure."""
import pytest

from plinta.pages.models import MenuGroup, MenuSection, Page
from plinta.shell.links import register_shell_link
from plinta.shell.menu import build
from tests.support import fresh, grant

pytestmark = pytest.mark.django_db


@pytest.fixture
def reader(ada):
    grant(ada, Page, "view")
    # A permission that exists only here, for the link tests below to name:
    # `plinta_pages.view_block`, minted on Page rather than Block so nothing
    # the pages app ships grants it by accident.
    grant(ada, Page, "view_block")
    return fresh(ada)


def page_in(group, name="Sales"):
    return Page.objects.create(name=name, slug=name.lower(), menu_group=group)


# --- the optional section ----------------------------------------------------


def test_a_group_with_no_section_sits_at_the_top(reader):
    """A small install has two levels rather than a heading it did not ask
    for."""
    page_in(MenuGroup.objects.create(name="Trading"))
    menu = build(reader)
    assert [s.name for s in menu] == [""]
    assert menu[0].is_top
    assert [g.name for g in menu[0].groups] == ["Trading"]


def test_a_section_still_groups_when_there_is_one(reader):
    section = MenuSection.objects.create(name="Bookshop")
    page_in(MenuGroup.objects.create(section=section, name="Trading"))
    assert [s.name for s in build(reader)] == ["Bookshop"]


def test_sectionless_groups_come_first(reader):
    """Deterministic across databases: a plain ascending sort puts NULL last
    on PostgreSQL and first on SQLite."""
    section = MenuSection.objects.create(name="Admin", order=0)
    page_in(MenuGroup.objects.create(section=section, name="Records"), "Audit")
    page_in(MenuGroup.objects.create(name="Trading"), "Sales")
    assert [s.name for s in build(reader)] == ["", "Admin"]


# --- links land where they say -----------------------------------------------


def test_a_link_joins_the_group_it_names(reader, shell_link_registry):
    """Both kinds of screen answer the same question, so a view sits beside a
    page instead of in a bucket of its own."""
    section = MenuSection.objects.create(name="Bookshop")
    group = MenuGroup.objects.create(section=section, name="Trading")
    page_in(group)
    register_shell_link(
        "builder", "Report builder", url_name="plinta:login",
        permission="plinta_pages.view_block",
        section="Bookshop", group="Trading",
    )
    trading = build(reader)[0].groups[0]
    assert [p.name for p in trading.pages] == ["Sales"]
    assert [link.label for link in trading.links] == ["Report builder"]


def test_a_link_can_make_a_group_of_its_own(reader, shell_link_registry):
    """An app shipping only a view needs no MenuGroup row."""
    register_shell_link(
        "builder", "Report builder", url_name="plinta:login",
        permission="plinta_pages.view_block",
        section="Reports", group="Tools",
    )
    menu = build(reader)
    assert [s.name for s in menu] == ["Reports"]
    assert [g.name for g in menu[0].groups] == ["Tools"]


def test_a_link_naming_nothing_sits_at_the_top(reader, shell_link_registry):
    register_shell_link(
        "builder", "Report builder", url_name="plinta:login",
        permission="plinta_pages.view_block",
    )
    assert build(reader)[0].is_top


def test_a_link_the_viewer_may_not_follow_is_absent(reader, shell_link_registry):
    register_shell_link(
        "secret", "Secret", url_name="plinta:login",
        permission="plinta_pages.delete_page", section="Admin", group="Tools",
    )
    assert build(reader) == []


def test_an_empty_section_is_not_drawn(reader, shell_link_registry):
    """An empty heading advertises something the viewer cannot reach."""
    MenuSection.objects.create(name="Bookshop")
    MenuGroup.objects.create(name="Trading")
    assert build(reader) == []

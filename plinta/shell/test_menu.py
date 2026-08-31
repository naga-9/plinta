"""The whole menu: pages and links in one structure."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.pages.models import MenuGroup, MenuSection, Page
from plinta.shell.links import register_shell_link
from plinta.shell.menu import build

pytestmark = pytest.mark.django_db


@pytest.fixture
def ada(db):
    user = User.objects.create(username="ada")
    for model, codename in ((Page, "view_page"),):
        perm, _ = Permission.objects.get_or_create(
            codename=codename,
            content_type=ContentType.objects.get_for_model(model),
            defaults={"name": codename},
        )
        user.user_permissions.add(perm)
    perm, _ = Permission.objects.get_or_create(
        codename="view_block",
        content_type=ContentType.objects.get_for_model(Page),
        defaults={"name": "view_block"},
    )
    user.user_permissions.add(perm)
    return User.objects.get(pk=user.pk)


def page_in(group, name="Sales"):
    return Page.objects.create(name=name, slug=name.lower(), menu_group=group)


# --- the optional section ----------------------------------------------------


def test_a_group_with_no_section_sits_at_the_top(ada):
    """A small install has two levels rather than a heading it did not ask
    for."""
    page_in(MenuGroup.objects.create(name="Trading"))
    menu = build(ada)
    assert [s.name for s in menu] == [""]
    assert menu[0].is_top
    assert [g.name for g in menu[0].groups] == ["Trading"]


def test_a_section_still_groups_when_there_is_one(ada):
    section = MenuSection.objects.create(name="Bookshop")
    page_in(MenuGroup.objects.create(section=section, name="Trading"))
    assert [s.name for s in build(ada)] == ["Bookshop"]


def test_sectionless_groups_come_first(ada):
    """Deterministic across databases: a plain ascending sort puts NULL last
    on PostgreSQL and first on SQLite."""
    section = MenuSection.objects.create(name="Admin", order=0)
    page_in(MenuGroup.objects.create(section=section, name="Records"), "Audit")
    page_in(MenuGroup.objects.create(name="Trading"), "Sales")
    assert [s.name for s in build(ada)] == ["", "Admin"]


# --- links land where they say -----------------------------------------------


def test_a_link_joins_the_group_it_names(ada, shell_link_registry):
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
    trading = build(ada)[0].groups[0]
    assert [p.name for p in trading.pages] == ["Sales"]
    assert [link.label for link in trading.links] == ["Report builder"]


def test_a_link_can_make_a_group_of_its_own(ada, shell_link_registry):
    """An app shipping only a view needs no MenuGroup row."""
    register_shell_link(
        "builder", "Report builder", url_name="plinta:login",
        permission="plinta_pages.view_block",
        section="Reports", group="Tools",
    )
    menu = build(ada)
    assert [s.name for s in menu] == ["Reports"]
    assert [g.name for g in menu[0].groups] == ["Tools"]


def test_a_link_naming_nothing_sits_at_the_top(ada, shell_link_registry):
    register_shell_link(
        "builder", "Report builder", url_name="plinta:login",
        permission="plinta_pages.view_block",
    )
    assert build(ada)[0].is_top


def test_a_link_the_viewer_may_not_follow_is_absent(ada, shell_link_registry):
    register_shell_link(
        "secret", "Secret", url_name="plinta:login",
        permission="plinta_pages.delete_page", section="Admin", group="Tools",
    )
    assert build(ada) == []


def test_an_empty_section_is_not_drawn(ada, shell_link_registry):
    """An empty heading advertises something the viewer cannot reach."""
    MenuSection.objects.create(name="Bookshop")
    MenuGroup.objects.create(name="Trading")
    assert build(ada) == []

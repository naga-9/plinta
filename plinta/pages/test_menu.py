"""The menu is what the viewer may open, and nothing else."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.pages.menu import build
from plinta.pages.models import MenuGroup, MenuSection, Page

pytestmark = pytest.mark.django_db


@pytest.fixture
def viewer(db):
    ada = User.objects.create(username="ada")
    perm, _ = Permission.objects.get_or_create(
        codename="view_page",
        content_type=ContentType.objects.get_for_model(Page),
        defaults={"name": "view page"},
    )
    ada.user_permissions.add(perm)
    return User.objects.get(pk=ada.pk)


@pytest.fixture
def nav(db):
    section = MenuSection.objects.create(name="Reference", order=1)
    return MenuGroup.objects.create(section=section, name="Catalog", order=1)


def page(group, owner, name="Catalog", **kwargs):
    return Page.objects.create(
        name=name, slug=name.lower(), owner=owner, menu_group=group, **kwargs
    )


def names(menu):
    return {
        section.section.name: {
            entry.group.name: [p.name for p in entry.pages] for entry in section.groups
        }
        for section in menu
    }


# --- what appears ----------------------------------------------------------


def test_a_page_appears_under_its_group(viewer, nav):
    page(nav, viewer)
    assert names(build(viewer)) == {"Reference": {"Catalog": ["Catalog"]}}


def test_a_public_page_appears(viewer, nav):
    page(nav, None, name="Shared")
    assert names(build(viewer)) == {"Reference": {"Catalog": ["Shared"]}}


def test_someone_elses_page_does_not(viewer, nav):
    """Permission-filtered by construction, not by a second configuration."""
    bob = User.objects.create(username="bob")
    page(nav, bob, name="Bobs")
    assert build(viewer) == []


def test_a_page_that_asks_to_be_hidden_does_not(viewer, nav):
    page(nav, viewer, show_in_menu=False)
    assert build(viewer) == []


def test_an_inactive_page_does_not(viewer, nav):
    page(nav, viewer, is_active=False)
    assert build(viewer) == []


def test_a_page_with_no_group_is_not_placed(viewer, nav):
    page(None, viewer)
    assert build(viewer) == []


def test_without_the_model_permission_the_menu_is_empty(nav, db):
    """Both permission tiers gate it, like every other read."""
    bob = User.objects.create(username="bob")
    page(nav, bob)
    assert build(bob) == []


# --- what is dropped -------------------------------------------------------


def test_a_group_with_no_visible_page_is_dropped(viewer, nav):
    """An empty heading advertises something the viewer cannot reach."""
    bob = User.objects.create(username="bob")
    page(nav, bob, name="Bobs")
    empty = MenuGroup.objects.create(section=nav.section, name="Empty")
    page(empty, viewer, name="Mine")
    assert names(build(viewer)) == {"Reference": {"Empty": ["Mine"]}}


def test_a_section_with_no_surviving_group_is_dropped(viewer, nav):
    other = MenuSection.objects.create(name="Admin", order=2)
    group = MenuGroup.objects.create(section=other, name="Settings")
    bob = User.objects.create(username="bob")
    page(group, bob, name="Bobs")
    page(nav, viewer, name="Mine")
    assert list(names(build(viewer))) == ["Reference"]


def test_no_pages_at_all_is_an_empty_menu(viewer, nav):
    assert build(viewer) == []


# --- ordering --------------------------------------------------------------


def test_sections_follow_their_order(viewer, nav):
    later = MenuSection.objects.create(name="Admin", order=0)
    group = MenuGroup.objects.create(section=later, name="Settings")
    page(group, viewer, name="Settings")
    page(nav, viewer, name="Mine")
    assert [s.section.name for s in build(viewer)] == ["Admin", "Reference"]


def test_groups_follow_their_order(viewer, nav):
    first = MenuGroup.objects.create(section=nav.section, name="First", order=0)
    page(first, viewer, name="A")
    page(nav, viewer, name="B")
    assert [e.group.name for e in build(viewer)[0].groups] == ["First", "Catalog"]


def test_a_section_lists_every_page_under_it(viewer, nav):
    other = MenuGroup.objects.create(section=nav.section, name="Other", order=2)
    page(nav, viewer, name="A")
    page(other, viewer, name="B")
    assert [p.name for p in build(viewer)[0].pages] == ["A", "B"]

"""The layout editor's control: registered, gated, and absent without a grid.

Core stores the four integers and owns the rule that writes them
(`composition.py`, tested there). The drag itself is a browser test. What is
worth checking here is the control: that it appears where a grid exists, and
asks for the same permission the positions endpoint checks.
"""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.pages.actions import registered, visible_actions
from plinta.pages.models import Page, PageBlock, PageType

pytestmark = pytest.mark.django_db


def grant(user, model, *codenames):
    content_type = ContentType.objects.get_for_model(model)
    for codename in codenames:
        permission, _ = Permission.objects.get_or_create(
            codename=codename, content_type=content_type, defaults={"name": codename}
        )
        user.user_permissions.add(permission)


def test_it_registers_a_page_action():
    assert "composer" in [action.name for action in registered()]


def test_the_control_needs_the_permission_the_write_checks():
    """The drag posts to `page_positions`, which asks for `change_pageblock`.
    Drawing a control that the write would refuse is worse than drawing
    none."""
    page = Page.objects.create(name="Sales", slug="sales")
    stranger = User.objects.create_user(username="sam", password="secret")  # noqa: S106
    assert visible_actions(page, stranger) == []

    author = User.objects.create_user(username="ada", password="secret")  # noqa: S106
    grant(author, PageBlock, "change_pageblock")
    author = User.objects.get(pk=author.pk)
    assert [a.name for a in visible_actions(page, author)] == ["composer"]


def test_it_is_absent_where_there_is_no_grid():
    """A detail page and a custom template have no placements to arrange."""
    author = User.objects.create_user(username="ada", password="secret")  # noqa: S106
    grant(author, PageBlock, "change_pageblock")
    author = User.objects.get(pk=author.pk)

    detail = Page.objects.create(name="Book", slug="book", page_type=PageType.DETAIL)
    assert visible_actions(detail, author) == []

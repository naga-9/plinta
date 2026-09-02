"""The composer is an enhancement, and the tests are mostly about that.

Core stores the four integers and owns the rule that writes them. This app
supplies dragging. So what is worth checking is that it adds nothing core
depends on: the control appears where a grid exists, it asks for the same
permission core checks, and the endpoint it posts to refuses whatever it
would refuse from a form.
"""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.pages.actions import registered, visible_actions
from plinta.pages.models import Page, PageType

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


def test_the_control_needs_the_permission_core_checks(db):
    """The drag posts to core, which asks for `change_pageblock`. Drawing a
    control that the write would refuse is worse than drawing none."""
    from plinta.pages.models import PageBlock

    page = Page.objects.create(name="Sales", slug="sales")
    stranger = User.objects.create_user(username="sam", password="secret")  # noqa: S106
    assert visible_actions(page, stranger) == []

    author = User.objects.create_user(username="ada", password="secret")  # noqa: S106
    grant(author, PageBlock, "change_pageblock")
    author = User.objects.get(pk=author.pk)
    assert [a.name for a in visible_actions(page, author)] == ["composer"]


def test_it_is_absent_where_there_is_no_grid(db):
    """A detail page and a custom template have no placements to arrange."""
    from plinta.pages.models import PageBlock

    author = User.objects.create_user(username="ada", password="secret")  # noqa: S106
    grant(author, PageBlock, "change_pageblock")
    author = User.objects.get(pk=author.pk)

    detail = Page.objects.create(
        name="Book", slug="book", page_type=PageType.DETAIL
    )
    assert visible_actions(detail, author) == []


def test_it_ships_no_models():
    """No models means no migrations and no permissions of its own — the
    whole app is a script, a stylesheet and one registration."""
    from django.apps import apps

    assert list(apps.get_app_config("plinta_composer").get_models()) == []


def test_its_script_is_local():
    """A remote script would break an offline install and a strict CSP, so
    core refuses one. This asserts we did not work around that."""
    from plinta.utils.assets import scripts

    paths = [script.path for script in scripts()]
    assert "composer/js/composer.js" in paths
    assert not any(path.startswith(("http://", "https://", "//")) for path in paths)

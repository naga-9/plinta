"""One command, and a consumer has an application (§13.2).

The two properties worth guarding are idempotency and delegation: running the
orchestrator twice must not double anything, and it must call a package's
seeder without core naming the package.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from plinta.blocks.models import Block
from plinta.datasources.models import DataSource, DataSourceField
from plinta.pages.models import MenuGroup, MenuSection, Page, PageBlock, PageFilter

pytestmark = pytest.mark.django_db


def counts():
    return (
        Page.objects.count(),
        Block.objects.count(),
        DataSource.objects.count(),
        PageBlock.objects.count(),
        PageFilter.objects.count(),
        MenuSection.objects.count(),
        MenuGroup.objects.count(),
    )


def test_one_command_seeds_the_platform():
    call_command("seed_platform_pages", verbosity=0)
    assert Page.objects.filter(slug="users").exists()
    assert MenuSection.objects.filter(name="Administration").exists()


def test_it_is_idempotent():
    """Run it twice; nothing doubles. Every seeder promises this, and the
    orchestrator is where a broken promise would show up first."""
    call_command("seed_platform_pages", verbosity=0)
    once = counts()
    call_command("seed_platform_pages", verbosity=0)
    assert counts() == once


def test_it_calls_only_what_is_installed(monkeypatch):
    """A contrib seeder is found through Django's command registry, so core
    never names the package that owns it."""
    called = []

    from plinta.pages.management.commands import seed_platform_pages as command

    monkeypatch.setattr(
        command, "get_commands", lambda: {"seed_users_page": "plinta.pages"}
    )
    monkeypatch.setattr(
        command, "call_command", lambda name, **kwargs: called.append(name)
    )
    call_command("seed_platform_pages", verbosity=0)

    # `seed_audit_page` is real but its app is not installed in this suite,
    # and asking rather than importing is what makes that a non-event.
    assert called == ["seed_users_page"]


def test_menu_only_creates_nothing_else():
    call_command("seed_platform_pages", "--menu-only", verbosity=0)
    assert MenuGroup.objects.exists()
    assert not Page.objects.exists()


# --- the users page ---------------------------------------------------------


def test_the_users_page_has_no_password_column():
    """A DataSourceField is the only thing that mints a field permission, so
    declaring one over `password` would make the hash showable (§5.7)."""
    call_command("seed_users_page", verbosity=0)
    source = DataSource.objects.get(name="users")
    names = set(source.fields.values_list("field_name", flat=True))
    assert "password" not in names
    assert "username" in names


def test_no_permission_exists_for_a_column_nobody_declared():
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    call_command("seed_users_page", verbosity=0)
    codenames = set(
        Permission.objects.filter(
            content_type=ContentType.objects.get_for_model(get_user_model())
        ).values_list("codename", flat=True)
    )
    assert "view_user_username" in codenames
    assert "view_user_password" not in codenames


def test_staff_is_readable_but_not_editable():
    """Granting Django-admin access from a dashboard cell is not a thing a
    dashboard cell should do."""
    call_command("seed_users_page", verbosity=0)
    staff = DataSourceField.objects.get(
        data_source__name="users", field_name="is_staff"
    )
    assert not staff.editable


def test_the_page_lands_in_the_menu():
    call_command("seed_platform_pages", verbosity=0)
    page = Page.objects.get(slug="users")
    assert page.menu_group.name == "People"
    assert page.menu_group.section.name == "Administration"


# --- the home screen --------------------------------------------------------


def test_home_lists_what_the_viewer_may_open(client, db):
    user = get_user_model().objects.create_user(
        username="ada", password="secret"  # noqa: S106
    )
    client.force_login(user)
    assert client.get("/").status_code == 200


def test_home_says_what_to_do_when_there_is_nothing(client, db):
    """A fresh install has no pages, and empty is a real state."""
    user = get_user_model().objects.create_user(
        username="ada", password="secret"  # noqa: S106
    )
    client.force_login(user)
    body = client.get("/").content.decode()
    assert "seed_platform_pages" in body

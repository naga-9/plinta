"""The orchestrator with real contrib apps installed (§13.2).

The core suite can only prove that discovery *works*; it installs no contrib
package, so nothing is there to discover. This is the other half: with
`audit`, `notifications` and `workflow` installed, one command must seed their
screens without core naming any of them.
"""
import pytest
from django.core.management import call_command

from plinta.blocks.models import Block
from plinta.datasources.models import DataSource
from plinta.pages.models import MenuGroup, MenuSection, Page, PageBlock, PageFilter

pytestmark = pytest.mark.django_db

#: What each installed package contributes. Named by slug rather than by
#: command, because a page is what a consumer actually gets.
SEEDED = ["users", "audit-trail", "notifications", "workflows"]


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


def test_one_command_seeds_every_installed_app():
    call_command("seed_platform_pages", verbosity=0)
    assert set(Page.objects.values_list("slug", flat=True)) >= set(SEEDED)


def test_it_is_idempotent_with_contrib_installed():
    call_command("seed_platform_pages", verbosity=0)
    once = counts()
    call_command("seed_platform_pages", verbosity=0)
    assert counts() == once


def test_every_seeded_page_hangs_from_a_group():
    """A page with no group never reaches the menu, which is a screen that
    exists and cannot be found."""
    call_command("seed_platform_pages", verbosity=0)
    for page in Page.objects.filter(slug__in=SEEDED):
        assert page.menu_group is not None, page.slug


def test_every_seeded_block_names_a_registered_component():
    """An unregistered component renders an empty slot rather than failing,
    so a typo here would ship a page of blank cards and no error."""
    from plinta.components.registry import is_registered

    call_command("seed_platform_pages", verbosity=0)
    for block in Block.objects.all():
        assert is_registered(block.component_type), block.name


def test_every_seeded_column_is_readable():
    """A DataSourceField naming a path the model cannot resolve is a column
    that raises at query time, on somebody else's screen."""
    from plinta.datasources.services import resolve_path

    call_command("seed_platform_pages", verbosity=0)
    for source in DataSource.objects.all():
        model = source.model
        for column in source.fields.all():
            resolve_path(model, column.field_name)


def test_notifications_stay_the_recipients():
    """The page adds no narrowing of its own; the app's policy is what makes
    this true, and seeding a DataSource must not widen it."""
    from django.contrib.auth.models import Permission, User
    from django.contrib.contenttypes.models import ContentType

    from plinta.contrib.notifications.models import Notification
    from plinta.permissions import allowed

    call_command("seed_platform_pages", verbosity=0)
    ada = User.objects.create_user(username="ada", password="secret")  # noqa: S106
    eve = User.objects.create_user(username="eve", password="secret")  # noqa: S106

    # Both hold the model permission, so what separates them below is the row
    # policy alone. Without this the test passes for the wrong reason: neither
    # sees anything, because both tiers must hold (§5.2).
    permission, _ = Permission.objects.get_or_create(
        codename="view_notification",
        content_type=ContentType.objects.get_for_model(Notification),
        defaults={"name": "view_notification"},
    )
    for person in (ada, eve):
        person.user_permissions.add(permission)
    ada = User.objects.get(pk=ada.pk)
    eve = User.objects.get(pk=eve.pk)

    Notification.objects.create(recipient=ada, kind="test", title="For ada")

    assert allowed(eve, "view", Notification.objects.all()).count() == 0
    assert allowed(ada, "view", Notification.objects.all()).count() == 1

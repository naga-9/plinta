"""Registering plinta's own shareable models.

The command exists to mint two permissions, so that is what the tests are
about — not the DataSource rows, which are the mechanism (§6.1b).
"""
import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command

from plinta.blocks.models import SavedView
from plinta.datasources.models import DataSource, DataSourceField
from plinta.pages.models import FilterSet

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded(db):
    call_command("seed_shareables")


def minted(codename: str) -> bool:
    return Permission.objects.filter(codename=codename).exists()


# --- what it is for ---------------------------------------------------------


def test_publishing_a_saved_view_becomes_a_permission(seeded):
    """`owner = None` is public, so publishing is a change to one field. With
    no DSF row there is no permission and any owner may publish unchecked."""
    assert minted("change_savedview_owner")


def test_publishing_a_filter_set_becomes_a_permission(seeded):
    assert minted("change_filterset_owner")


def test_a_column_that_is_not_editable_mints_only_view(seeded):
    """`block` is shown and never rewritten: a view belongs to the block it
    was saved on."""
    assert minted("view_savedview_block")
    assert not minted("change_savedview_block")


# --- the registration itself ------------------------------------------------


def test_both_models_are_registered(seeded):
    for model in (SavedView, FilterSet):
        assert DataSource.objects.filter(
            content_type=ContentType.objects.get_for_model(model)
        ).exists()


def test_a_configuration_model_is_not(seeded):
    """Block, Page and DataSource are authoring screens, gated whole rather
    than field by field (§6.1b)."""
    from plinta.blocks.models import Block
    from plinta.pages.models import Page

    for model in (Block, Page, DataSource):
        assert not DataSource.objects.filter(
            content_type=ContentType.objects.get_for_model(model)
        ).exists()


def test_running_it_twice_changes_nothing(seeded):
    """Idempotent, like every seeder (§13.2)."""
    sources = DataSource.objects.count()
    fields = DataSourceField.objects.count()
    permissions = Permission.objects.count()

    call_command("seed_shareables")

    assert DataSource.objects.count() == sources
    assert DataSourceField.objects.count() == fields
    assert Permission.objects.count() == permissions


def test_a_second_run_keeps_the_grants(seeded):
    """The reason to check: delete-and-recreate silently drops every grant,
    which is the failure §5.7 calls out for renames."""
    from django.contrib.auth.models import User

    ada = User.objects.create_user(username="ada", password="x")  # noqa: S106
    ada.user_permissions.add(Permission.objects.get(codename="change_savedview_owner"))

    call_command("seed_shareables")

    assert User.objects.get(pk=ada.pk).has_perm(
        "plinta_blocks.change_savedview_owner"
    )

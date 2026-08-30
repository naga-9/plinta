"""Registering an action beyond Django's four, and minting it per model."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.permissions.actions import (
    DJANGO_ACTIONS,
    ActionError,
    mint_action,
    mint_for,
)
from plinta.permissions.engine import can
from plinta.permissions.policies import PermissionPolicy
from plinta.permissions.rules import Owner, Public
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db


def codenames(model=Book):
    ct = ContentType.objects.get_for_model(model)
    return set(Permission.objects.filter(content_type=ct).values_list("codename", flat=True))


# --- registering -----------------------------------------------------------


def test_registers_an_action(action_registry):
    action = action_registry.register_action("import", "import into")
    assert action.name == "import" and action.label == "import into"
    assert set(action_registry.registered()) == {"import"}


def test_the_label_defaults_to_the_name(action_registry):
    assert action_registry.register_action("export").label == "export"


@pytest.mark.parametrize("name", list(DJANGO_ACTIONS))
def test_djangos_own_actions_are_refused(action_registry, name):
    """Registering one would shadow a permission Django already mints."""
    with pytest.raises(ActionError, match="minted by Django"):
        action_registry.register_action(name)


@pytest.mark.parametrize("name", ["Import", "1st", "with-dash", "", "with space"])
def test_an_unusable_name_is_refused(action_registry, name):
    with pytest.raises(ActionError):
        action_registry.register_action(name)


def test_a_duplicate_is_refused(action_registry):
    action_registry.register_action("import")
    with pytest.raises(ActionError, match="already registered"):
        action_registry.register_action("import")


def test_a_capability_does_not_filter_rows_by_default(action_registry):
    """`export` composes with view's filter; there is no exportable-rows set."""
    assert action_registry.register_action("export").filters_rows is False


def test_a_row_action_says_so(action_registry):
    assert action_registry.register_action("archive", filters_rows=True).filters_rows is True


# --- minting ---------------------------------------------------------------


def test_minting_creates_the_permission(action_registry):
    action_registry.register_action("import")
    assert mint_action(Book, "import") is True
    assert "import_book" in codenames()


def test_minting_twice_creates_one(action_registry):
    action_registry.register_action("import")
    assert mint_action(Book, "import") is True
    assert mint_action(Book, "import") is False


def test_an_unregistered_action_is_refused(action_registry):
    """Otherwise the console offers a permission nothing ever checks."""
    with pytest.raises(ActionError, match="not registered"):
        mint_action(Book, "import")


def test_mint_for_covers_every_registered_action(action_registry):
    action_registry.register_action("import")
    action_registry.register_action("export")
    assert mint_for(Book) == ["export", "import"]
    assert {"import_book", "export_book"} <= codenames()


def test_minting_is_per_model(action_registry):
    action_registry.register_action("import")
    mint_for(Book)
    assert "import_book" in codenames(Book)
    assert "import_region" not in codenames(Region)


def test_the_permission_carries_the_label(action_registry):
    action_registry.register_action("import", "import into")
    mint_action(Book, "import")
    assert Permission.objects.get(codename="import_book").name == "Can import into book"


# --- using it --------------------------------------------------------------


def test_a_new_action_needs_no_core_change_to_check(action_registry, db):
    """The whole point: can() takes any action string."""
    action_registry.register_action("import")
    mint_for(Book)
    ada = User.objects.create(username="ada")

    assert can(ada, "import", Book) is False
    ada.user_permissions.add(Permission.objects.get(codename="import_book"))
    assert can(User.objects.get(pk=ada.pk), "import", Book) is True


def test_a_capability_falls_back_to_the_model_permission(action_registry, policy_registry, db):
    """A policy silent on `import` lets import_book decide alone."""
    class BookPolicy(PermissionPolicy):
        view = Owner() | Public()

    policy_registry.register_policy(Book, BookPolicy)
    action_registry.register_action("import")
    mint_for(Book)

    ada = User.objects.create(username="ada")
    ada.user_permissions.add(Permission.objects.get(codename="import_book"))
    ada = User.objects.get(pk=ada.pk)
    book = Book.objects.create(title="Emma", owner=None)

    assert can(ada, "import", book) is True, "no rule for import, so the permission decides"


def test_a_policy_may_still_narrow_one(action_registry, policy_registry, db):
    class BookPolicy(PermissionPolicy):
        archive = Owner()

    policy_registry.register_policy(Book, BookPolicy)
    action_registry.register_action("archive", filters_rows=True)
    mint_for(Book)

    ada = User.objects.create(username="ada")
    bob = User.objects.create(username="bob")
    ada.user_permissions.add(Permission.objects.get(codename="archive_book"))
    ada = User.objects.get(pk=ada.pk)

    assert can(ada, "archive", Book.objects.create(title="Dune", owner=ada)) is True
    assert can(ada, "archive", Book.objects.create(title="Emma", owner=bob)) is False

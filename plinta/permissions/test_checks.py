"""The boot check: a policy naming a permission nobody minted."""
import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from plinta.permissions.checks import check_haspermissions_exist, declared_codenames
from plinta.permissions.policies import PermissionPolicy
from plinta.permissions.rules import HasPerm, Owner, Public, walk
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db


def mint(codename, model=Book):
    ct = ContentType.objects.get_for_model(model)
    Permission.objects.get_or_create(
        content_type=ct, codename=codename, defaults={"name": codename}
    )


# --- walking a rule tree ---------------------------------------------------


def test_walk_visits_every_node():
    rule = Owner() | (Public() & HasPerm("testapp.publish_book"))
    assert len(list(walk(rule))) == 5, "two combinators and three leaves"


def test_walk_yields_a_leaf_alone():
    rule = Owner()
    assert list(walk(rule)) == [rule]


def test_walk_finds_a_nested_hasperm():
    rule = Owner() | (Public() & HasPerm("testapp.publish_book"))
    found = [n.codename for n in walk(rule) if isinstance(n, HasPerm)]
    assert found == ["testapp.publish_book"]


# --- collecting what policies declare --------------------------------------


def test_declared_codenames_reports_where_each_came_from(policy_registry):
    class BookPolicy(PermissionPolicy):
        view = Owner() | Public()
        change = Owner() | HasPerm("testapp.change_book_owner")

    policy_registry.register_policy(Book, BookPolicy)
    assert declared_codenames() == {(Book, "change", "testapp.change_book_owner")}


def test_declared_codenames_is_empty_with_no_policies(policy_registry):
    assert declared_codenames() == set()


def test_declared_codenames_ignores_a_policy_with_no_hasperm(policy_registry):
    class Simple(PermissionPolicy):
        view = Owner() | Public()

    policy_registry.register_policy(Book, Simple)
    assert declared_codenames() == set()


def test_declared_codenames_covers_every_model(policy_registry):
    class BookPolicy(PermissionPolicy):
        view = HasPerm("testapp.read_books")

    class RegionPolicy(PermissionPolicy):
        view = HasPerm("testapp.read_regions")

    policy_registry.register_policy(Book, BookPolicy)
    policy_registry.register_policy(Region, RegionPolicy)
    assert {c for _, _, c in declared_codenames()} == {
        "testapp.read_books", "testapp.read_regions"
    }


# --- the check itself ------------------------------------------------------


def test_a_missing_permission_is_an_error(policy_registry):
    class BookPolicy(PermissionPolicy):
        change = HasPerm("testapp.nobody_minted_this")

    policy_registry.register_policy(Book, BookPolicy)
    errors = check_haspermissions_exist()

    assert len(errors) == 1
    assert errors[0].id == "plinta.permissions.E001"
    assert "nobody_minted_this" in errors[0].msg
    assert "deny every row" in errors[0].msg, "says what goes wrong, not just what is missing"


def test_a_minted_permission_passes(policy_registry):
    mint("change_book_owner")

    class BookPolicy(PermissionPolicy):
        change = HasPerm("testapp.change_book_owner")

    policy_registry.register_policy(Book, BookPolicy)
    assert check_haspermissions_exist() == []


def test_no_policies_means_nothing_to_check(policy_registry):
    assert check_haspermissions_exist() == []


def test_the_error_names_the_model_and_the_action(policy_registry):
    class BookPolicy(PermissionPolicy):
        change = HasPerm("testapp.missing")

    policy_registry.register_policy(Book, BookPolicy)
    msg = check_haspermissions_exist()[0].msg
    assert "Book" in msg and "change" in msg


def test_several_missing_permissions_are_all_reported(policy_registry):
    class BookPolicy(PermissionPolicy):
        view = HasPerm("testapp.missing_one")
        change = HasPerm("testapp.missing_two")

    policy_registry.register_policy(Book, BookPolicy)
    assert len(check_haspermissions_exist()) == 2


def test_a_nested_hasperm_is_checked(policy_registry):
    """A rule buried in a tree denies just as effectively as one at the top."""

    class BookPolicy(PermissionPolicy):
        view = Owner() | (Public() & HasPerm("testapp.missing"))

    policy_registry.register_policy(Book, BookPolicy)
    assert len(check_haspermissions_exist()) == 1


def test_the_app_label_matters(policy_registry):
    """`auth.missing` and `testapp.missing` are different permissions."""
    mint("missing")

    class BookPolicy(PermissionPolicy):
        view = HasPerm("auth.missing")

    policy_registry.register_policy(Book, BookPolicy)
    assert len(check_haspermissions_exist()) == 1


def test_the_check_is_registered_with_django():
    from django.core.checks import registry

    assert check_haspermissions_exist in registry.registry.get_checks()

"""The escalation rule: you cannot hand out what you do not hold."""
import pytest
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.permissions.grants import (
    PermissionEscalation,
    add_to_group,
    can_add_to_group,
    can_grant,
    grant,
    grantable,
    remove_from_group,
    revoke,
)
from tests.testapp.models import Book

pytestmark = pytest.mark.django_db


@pytest.fixture
def perms(db):
    ct = ContentType.objects.get_for_model(Book)
    return {
        name: Permission.objects.get_or_create(
            codename=name, content_type=ct, defaults={"name": name}
        )[0]
        for name in ("view_book", "change_book", "delete_book", "publish_book")
    }


def reload(user):
    """Django caches a user's permissions for the life of the instance."""
    return User.objects.get(pk=user.pk)


@pytest.fixture
def ada(db, perms):
    user = User.objects.create(username="ada")
    user.user_permissions.add(perms["view_book"], perms["change_book"])
    return reload(user)


@pytest.fixture
def bob(db):
    return User.objects.create(username="bob")


@pytest.fixture
def root(db):
    return User.objects.create(username="root", is_superuser=True)


# --- what may be granted ---------------------------------------------------


def test_a_user_may_grant_what_they_hold(ada, perms):
    assert can_grant(ada, perms["view_book"]) is True


def test_a_user_may_not_grant_what_they_lack(ada, perms):
    assert can_grant(ada, perms["delete_book"]) is False


def test_a_superuser_may_grant_anything(root, perms):
    assert all(can_grant(root, p) for p in perms.values())


def test_a_permission_held_through_a_group_may_be_granted(bob, perms):
    admins = Group.objects.create(name="admins")
    admins.permissions.add(perms["delete_book"])
    bob.groups.add(admins)
    assert can_grant(reload(bob), perms["delete_book"]) is True


def test_grantable_narrows_to_what_the_granter_holds(ada, perms):
    offered = grantable(ada, perms.values())
    assert {p.codename for p in offered} == {"view_book", "change_book"}


# --- granting --------------------------------------------------------------


def test_granting_what_you_hold_works(ada, bob, perms):
    assert grant(ada, bob, [perms["view_book"]]) == [perms["view_book"]]
    assert reload(bob).has_perm("testapp.view_book")


def test_granting_what_you_lack_raises(ada, bob, perms):
    with pytest.raises(PermissionEscalation, match="delete_book"):
        grant(ada, bob, [perms["delete_book"]])


def test_a_refused_grant_applies_nothing(ada, bob, perms):
    """All or nothing: a partial grant leaves the caller unable to tell what happened."""
    with pytest.raises(PermissionEscalation):
        grant(ada, bob, [perms["view_book"], perms["delete_book"]])
    assert not reload(bob).has_perm("testapp.view_book")


def test_the_error_names_every_refused_permission(ada, bob, perms):
    with pytest.raises(PermissionEscalation) as exc:
        grant(ada, bob, [perms["delete_book"], perms["publish_book"]])
    assert exc.value.codenames == ["testapp.delete_book", "testapp.publish_book"]


def test_granting_to_yourself_obeys_the_same_rule(ada, perms):
    """The defect this closes: an administrator promoting themselves."""
    with pytest.raises(PermissionEscalation):
        grant(ada, ada, [perms["delete_book"]])


def test_a_superuser_may_grant_anything_to_anyone(root, bob, perms):
    grant(root, bob, list(perms.values()))
    assert reload(bob).has_perm("testapp.delete_book")


def test_granting_something_already_held_is_not_an_error(ada, bob, perms):
    grant(ada, bob, [perms["view_book"]])
    assert grant(ada, bob, [perms["view_book"]]) == []


def test_granting_to_a_group_works(ada, perms):
    readers = Group.objects.create(name="readers")
    assert grant(ada, readers, [perms["view_book"]]) == [perms["view_book"]]
    assert readers.permissions.count() == 1


def test_granting_to_a_group_obeys_the_same_rule(ada, perms):
    """A group grant reaches every member, so it cannot be looser."""
    readers = Group.objects.create(name="readers")
    with pytest.raises(PermissionEscalation):
        grant(ada, readers, [perms["delete_book"]])


def test_granting_to_something_that_holds_no_permissions_is_a_type_error(ada, perms):
    with pytest.raises(TypeError):
        grant(ada, Book.objects.create(title="Dune"), [perms["view_book"]])


# --- revoking is unrestricted ----------------------------------------------


def test_revoking_what_you_do_not_hold_is_allowed(ada, bob, perms):
    """Removing access cannot escalate anyone."""
    bob.user_permissions.add(perms["delete_book"])
    assert revoke(ada, bob, [perms["delete_book"]]) == [perms["delete_book"]]
    assert not reload(bob).has_perm("testapp.delete_book")


def test_revoking_something_not_held_is_not_an_error(ada, bob, perms):
    assert revoke(ada, bob, [perms["view_book"]]) == []


def test_revoking_from_a_group(ada, perms):
    readers = Group.objects.create(name="readers")
    readers.permissions.add(perms["delete_book"])
    assert revoke(ada, readers, [perms["delete_book"]]) == [perms["delete_book"]]


# --- group membership ------------------------------------------------------


def test_adding_to_a_group_needs_everything_the_group_carries(ada, bob, perms):
    admins = Group.objects.create(name="admins")
    admins.permissions.add(perms["view_book"], perms["delete_book"])
    with pytest.raises(PermissionEscalation, match="delete_book"):
        add_to_group(ada, bob, admins)


def test_adding_to_a_group_you_could_have_granted_works(ada, bob, perms):
    readers = Group.objects.create(name="readers")
    readers.permissions.add(perms["view_book"])
    assert add_to_group(ada, bob, readers) is True
    assert reload(bob).has_perm("testapp.view_book")


def test_the_group_name_does_not_decide(ada, bob, perms):
    """"Read only" carrying delete_book is exactly what a name-based rule misses."""
    trap = Group.objects.create(name="Read only")
    trap.permissions.add(perms["delete_book"])
    assert can_add_to_group(ada, trap) is False


def test_an_empty_group_may_be_joined_by_anyone(ada, bob):
    assert can_add_to_group(ada, Group.objects.create(name="empty")) is True


def test_a_superuser_may_add_to_any_group(root, bob, perms):
    admins = Group.objects.create(name="admins")
    admins.permissions.add(perms["delete_book"])
    assert add_to_group(root, bob, admins) is True


def test_adding_to_a_group_twice_changes_nothing(ada, bob):
    empty = Group.objects.create(name="empty")
    assert add_to_group(ada, bob, empty) is True
    assert add_to_group(ada, bob, empty) is False


def test_removing_from_a_group_is_unrestricted(ada, bob, perms):
    admins = Group.objects.create(name="admins")
    admins.permissions.add(perms["delete_book"])
    bob.groups.add(admins)
    assert remove_from_group(ada, bob, admins) is True
    assert not reload(bob).has_perm("testapp.delete_book")


def test_removing_from_a_group_they_are_not_in(ada, bob):
    assert remove_from_group(ada, bob, Group.objects.create(name="empty")) is False


# --- the escalation path, end to end ---------------------------------------


def test_an_administrator_cannot_promote_themselves(ada, perms):
    """v1's apply path took `actor` for the audit row and never checked it."""
    before = set(reload(ada).get_all_permissions())

    for attempt in (
        lambda: grant(ada, ada, [perms["delete_book"]]),
        lambda: grant(ada, ada, [perms["publish_book"]]),
    ):
        with pytest.raises(PermissionEscalation):
            attempt()

    assert set(reload(ada).get_all_permissions()) == before


def test_nor_through_a_group_they_create(ada, perms):
    """The indirect route: make a powerful group, then join it."""
    trap = Group.objects.create(name="mine")
    with pytest.raises(PermissionEscalation):
        grant(ada, trap, [perms["delete_book"]])

    trap.permissions.add(perms["delete_book"])      # planted another way
    with pytest.raises(PermissionEscalation):
        add_to_group(ada, ada, trap)

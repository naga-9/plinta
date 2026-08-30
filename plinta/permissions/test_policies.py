"""Declaring a policy, registering it, and asking it what governs an action."""
import pytest

from plinta.permissions.policies import (
    PermissionPolicy,
    PolicyError,
    policy_for,
    register_policy,
    registered,
)
from plinta.permissions.rules import AllowAll, FieldEq, Owner, Public, Rule
from tests.testapp.models import Book, Region


class BookPolicy(PermissionPolicy):
    view = Owner() | Public()
    change = Owner()


# --- declaring -------------------------------------------------------------


def test_rule_for_returns_the_declared_rule():
    assert isinstance(BookPolicy().rule_for("view"), Rule)


def test_rule_for_is_none_when_the_policy_is_silent():
    """Silence is not denial — the model permission decides that action."""
    assert BookPolicy().rule_for("delete") is None


def test_a_non_rule_attribute_is_not_a_rule():
    """So a policy may carry helpers and constants without them becoming actions."""

    class WithExtras(PermissionPolicy):
        view = Owner()
        default_owner_field = "owner"

        def helper(self):
            return None

    policy = WithExtras()
    assert policy.rule_for("default_owner_field") is None
    assert policy.rule_for("helper") is None
    assert policy.actions() == {"view"}


def test_actions_lists_only_what_is_declared():
    assert BookPolicy().actions() == {"view", "change"}


def test_a_policy_with_no_rules_declares_nothing():
    class Empty(PermissionPolicy):
        pass

    assert Empty().actions() == set()


def test_a_subclass_inherits_its_parent_rules_and_may_override():
    class Stricter(BookPolicy):
        change = Owner() & FieldEq("in_print", True)

    policy = Stricter()
    assert policy.actions() == {"view", "change"}
    assert isinstance(policy.rule_for("view"), Rule), "inherited from BookPolicy"
    assert repr(policy.rule_for("change")) != repr(BookPolicy().rule_for("change"))


def test_a_subclass_may_add_an_action():
    class WithPublish(BookPolicy):
        publish = AllowAll()

    assert WithPublish().actions() == {"view", "change", "publish"}


# --- registering -----------------------------------------------------------


def test_registering_a_class_instantiates_it(policy_registry):
    assert isinstance(policy_registry.register_policy(Book, BookPolicy), BookPolicy)


def test_registering_an_instance_keeps_it(policy_registry):
    policy = BookPolicy()
    assert policy_registry.register_policy(Book, policy) is policy


def test_a_model_cannot_have_two_policies(policy_registry):
    policy_registry.register_policy(Book, BookPolicy)
    with pytest.raises(PolicyError, match="already has"):
        policy_registry.register_policy(Book, BookPolicy)


@pytest.mark.parametrize("bad", [object(), "BookPolicy", None, Owner()])
def test_something_that_is_not_a_policy_is_refused(policy_registry, bad):
    with pytest.raises(PolicyError, match="not a PermissionPolicy"):
        policy_registry.register_policy(Book, bad)


def test_two_models_may_have_their_own(policy_registry):
    policy_registry.register_policy(Book, BookPolicy)
    policy_registry.register_policy(Region, BookPolicy)
    assert policy_registry.policy_for(Book) is not policy_registry.policy_for(Region)


# --- looking up ------------------------------------------------------------


def test_policy_for_returns_the_registered_policy(policy_registry):
    policy = policy_registry.register_policy(Book, BookPolicy)
    assert policy_registry.policy_for(Book) is policy


def test_policy_for_is_none_when_none_is_registered(policy_registry):
    """Which means row control is not in use, and the model permission decides."""
    assert policy_registry.policy_for(Book) is None


def test_registered_lists_every_model_with_a_policy(policy_registry):
    policy_registry.register_policy(Book, BookPolicy)
    assert set(policy_registry.registered()) == {Book}


def test_registered_returns_a_copy(policy_registry):
    """Handing out the registry itself would let a caller corrupt it."""
    policy_registry.register_policy(Book, BookPolicy)
    policy_registry.registered().clear()
    assert policy_registry.policy_for(Book) is not None


def test_the_module_level_functions_reach_the_same_registry(policy_registry):
    register_policy(Book, BookPolicy)
    assert policy_for(Book) is not None
    assert set(registered()) == {Book}

"""Policies: which rule governs which action, per model.

A policy is declared as class attributes named after actions, and registered
against a model. Registration rather than a model attribute, so a consumer's
models stay plain Django.
"""
from __future__ import annotations

from plinta.permissions.rules import Rule


class PermissionPolicy:
    """Rules per action. An attribute name is the action it governs.

        class BookPolicy(PermissionPolicy):
            view = Owner() | Public()
            change = Owner()

    An action with no attribute is **not denied** — the model permission alone
    decides it. Declaring `view` says nothing about `change`.
    """

    def rule_for(self, action: str) -> Rule | None:
        """The rule governing ``action``, or None if this policy is silent on it."""
        rule = getattr(self, action, None)
        return rule if isinstance(rule, Rule) else None

    def actions(self) -> set[str]:
        """Every action this policy declares a rule for."""
        return {
            name
            for name in dir(self)
            if not name.startswith("_") and isinstance(getattr(self, name, None), Rule)
        }


class PolicyError(Exception):
    """A model was given two policies, or something that is not a policy."""


_registry: dict[type, PermissionPolicy] = {}


def register_policy(model: type, policy: PermissionPolicy | type[PermissionPolicy]) -> PermissionPolicy:
    """Register the policy governing ``model``.

    Accepts an instance or the class, since a policy holds no per-call state.

    Raises:
        PolicyError: the model already has one, or ``policy`` is not a
            ``PermissionPolicy``.
    """
    if isinstance(policy, type):
        policy = policy()
    if not isinstance(policy, PermissionPolicy):
        raise PolicyError(f"{policy!r} is not a PermissionPolicy")
    if model in _registry:
        raise PolicyError(f"{model.__name__} already has {_registry[model]!r}")
    _registry[model] = policy
    return policy


def policy_for(model: type) -> PermissionPolicy | None:
    """The policy governing ``model``, or None.

    None means row-level control is not in use for this model, and the model
    permission decides alone (§5.3). It fails open by design, which is why the
    startup check reports every model without one.
    """
    return _registry.get(model)


def registered() -> dict[type, PermissionPolicy]:
    """Every model with a policy."""
    return dict(_registry)

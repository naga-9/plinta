"""The access engine.

Everything in plinta calls ``can``, ``allowed`` and ``fields``.
"""
from plinta.permissions.engine import allowed, can, explain, fields
from plinta.permissions.policies import (
    PermissionPolicy,
    PolicyError,
    policy_for,
    register_policy,
)
from plinta.permissions.rules import (
    DENY,
    AllowAll,
    Callable,
    FieldEq,
    FieldInUserSet,
    GroupOverlap,
    HasPerm,
    InstancePerm,
    Owner,
    ParentModelPerm,
    Public,
    Rule,
    UserInM2M,
)

__all__ = [
    "DENY",
    "PermissionPolicy",
    "PolicyError",
    "allowed",
    "can",
    "explain",
    "fields",
    "policy_for",
    "register_policy",
    "AllowAll",
    "Callable",
    "FieldEq",
    "FieldInUserSet",
    "GroupOverlap",
    "HasPerm",
    "InstancePerm",
    "Owner",
    "ParentModelPerm",
    "Public",
    "Rule",
    "UserInM2M",
]

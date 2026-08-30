"""The access engine.

Everything in plinta calls ``can``, ``allowed`` and ``fields``.
"""
from plinta.permissions.engine import allowed, can, explain, fields
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
from plinta.permissions.fields import (
    FieldPermissionError,
    minted_fields,
    remove_field,
    rename_field,
    sync_field,
    sync_model,
)
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
    "FieldPermissionError",
    "PermissionEscalation",
    "PermissionPolicy",
    "PolicyError",
    "add_to_group",
    "allowed",
    "can",
    "can_add_to_group",
    "can_grant",
    "explain",
    "fields",
    "grant",
    "grantable",
    "minted_fields",
    "policy_for",
    "register_policy",
    "remove_field",
    "remove_from_group",
    "rename_field",
    "revoke",
    "sync_field",
    "sync_model",
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

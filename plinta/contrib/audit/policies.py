"""Who may read the trail.

Read-only by construction: there is no `change` or `delete` rule, so the model
permission alone would decide them — and a consumer who grants
`change_auditentry` to anybody has defeated the point of keeping one.
"""
from plinta.contrib.audit.models import AuditEntry
from plinta.permissions.policies import PermissionPolicy, register_policy
from plinta.permissions.rules import AllowAll


class AuditEntryPolicy(PermissionPolicy):
    """Every entry, to anyone holding `view_auditentry`.

    Deliberately unfiltered: an audit trail narrowed per viewer is a trail that
    cannot be reconciled, and the decision of who may read it belongs to the
    model permission rather than to a row rule.
    """

    view = AllowAll()


register_policy(AuditEntry, AuditEntryPolicy)

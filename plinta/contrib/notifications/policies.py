"""A notification is the recipient's, and nobody else's."""
from plinta.contrib.notifications.models import (
    Notification,
    NotificationPreference,
    QueuedEmail,
)
from plinta.permissions.policies import PermissionPolicy, register_policy
from plinta.permissions.rules import Owner


class NotificationPolicy(PermissionPolicy):
    """Yours alone — there is no sharing a notification and no public one.

    `Owner` on `recipient` rather than a field called `owner`: the rule takes
    the field name because a consumer's idea of ownership is theirs to name.
    """

    view = Owner("recipient")
    change = Owner("recipient")
    delete = Owner("recipient")


class NotificationPreferencePolicy(PermissionPolicy):
    view = Owner("user")
    change = Owner("user")
    delete = Owner("user")


register_policy(Notification, NotificationPolicy)
register_policy(NotificationPreference, NotificationPreferencePolicy)
# QueuedEmail has no policy: it is operational, not personal, and reading it
# needs the model permission alone — which is a deliberate grant.
assert QueuedEmail is not None

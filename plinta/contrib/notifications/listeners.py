"""Three receivers, and the mapping from a core event to a subscription's.

`object_written` carries `mode`, so one signal answers three event names — a
subscription may care about creates only, updates only, or both.
"""
from __future__ import annotations

from plinta.contrib.notifications.delivery import notify
from plinta.events import signals


def on_written(sender, obj, mode, changes, actor=None, source="", **kwargs):
    """A completed write, offered under both its specific name and `written`.

    So a subscription can say "when a sale is created" or "whenever a sale is
    touched" without core needing two signals for it.
    """
    payload = {"changes": changes, "actor": actor, "source": source, "mode": mode}
    notify(obj, "created" if mode == "create" else "updated", **payload)
    notify(obj, "written", **payload)


def on_deleted(sender, obj, pk, actor=None, source="", **kwargs):
    notify(obj, "deleted", pk=pk, actor=actor, source=source)


def on_state_changed(sender, obj, from_state, to_state, actor=None, source="", **kwargs):
    """A transition. `notifications` never imports `workflow` to read it."""
    notify(
        obj, "state_changed",
        from_state=from_state, to_state=to_state, actor=actor, source=source,
    )


def on_comment_posted(sender, obj, body="", metadata=None, actor=None, source="", **kwargs):
    """A comment on a row. `notifications` never imports `comments` for it:
    the signal carries what a subscription needs."""
    notify(
        obj, "comment_posted",
        body=body, metadata=metadata or {}, actor=actor, source=source,
    )


#: Registered under a uid, so connecting twice is harmless and disconnecting
#: is possible. A uid must be matched to remove it.
SUBSCRIPTIONS = (
    (signals.object_written, on_written, "plinta.notifications.written"),
    (signals.object_deleted, on_deleted, "plinta.notifications.deleted"),
    (signals.state_changed, on_state_changed, "plinta.notifications.state"),
    (signals.comment_posted, on_comment_posted, "plinta.notifications.comment"),
)


def connect() -> None:
    """Subscribe. Called from `AppConfig.ready()`."""
    for signal, receiver, uid in SUBSCRIPTIONS:
        signal.connect(receiver, dispatch_uid=uid)


def disconnect() -> None:
    """Stop listening, without uninstalling the app."""
    for signal, _receiver, uid in SUBSCRIPTIONS:
        signal.disconnect(dispatch_uid=uid)


connect()

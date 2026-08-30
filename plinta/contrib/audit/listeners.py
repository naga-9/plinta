"""The whole of the app's coupling: three receivers on signals it does not own.

Nothing in core imports this module, and nothing in core knows an audit trail
exists. That is the difference between a listener and a pipeline stage, and it
is what the event bus was built for (§4.10).
"""
from __future__ import annotations

import logging
from typing import Any

from django.contrib.contenttypes.models import ContentType

from plinta.events import signals

logger = logging.getLogger(__name__)

#: Fields never recorded, whatever a write says about them. A password hash in
#: an audit trail is a password hash in a second place.
REDACTED = frozenset({"password", "secret", "token", "api_key", "private_key"})

#: How long a stored label may be, matching the column.
LABEL = 200

#: App labels never recorded. Plinta's own configuration changes constantly —
#: somebody dragging a block, somebody saving a view — and a trail of that
#: buries the writes an audit exists to show. A consumer's models are recorded
#: unless they say otherwise, because a trail you forgot to switch on is
#: silent, and silence is the failure that matters here.
DEFAULT_EXCLUDED_APPS = frozenset(
    {
        "plinta_blocks",
        "plinta_pages",
        "plinta_datasources",
        "plinta_audit",
        "sessions",
        "contenttypes",
    }
)


def excluded_apps() -> frozenset[str]:
    """App labels this installation does not record."""
    from django.conf import settings

    declared = getattr(settings, "PLINTA_AUDIT_EXCLUDE_APPS", None)
    return DEFAULT_EXCLUDED_APPS if declared is None else frozenset(declared)


def records(obj: Any) -> bool:
    """Whether a write to this model is worth an entry."""
    try:
        return obj._meta.app_label not in excluded_apps()
    except AttributeError:
        return False


def describe(obj: Any) -> str:
    """What this row was, in words.

    Kept alongside the generic relation because a deleted row leaves that
    relation dangling, and an entry that cannot say what it was about is not
    an audit trail. A model whose ``__str__`` raises is still worth an entry,
    so the failure is swallowed here rather than losing the write.
    """
    try:
        return str(obj)[:LABEL]
    except Exception:  # noqa: BLE001 - a consumer's __str__ is not ours to trust
        return f"{type(obj).__name__} (unprintable)"


def scrub(changes: dict[str, Any]) -> dict[str, Any]:
    """The diff, with anything sensitive replaced rather than dropped.

    Dropped, the entry would say nothing changed. Replaced, it says the field
    changed and declines to say to what — which is the true and useful answer.
    """
    return {
        name: ("[redacted]", "[redacted]") if _sensitive(name) else value
        for name, value in (changes or {}).items()
    }


def _sensitive(name: str) -> bool:
    lowered = name.lower()
    return any(word in lowered for word in REDACTED)


def _record(action: str, obj: Any, *, pk=None, actor=None, source="", changes=None):
    """Write one entry, if this model is recorded at all.

    Never raises into the write that caused it.
    """
    from plinta.contrib.audit.models import AuditEntry

    if not records(obj):
        return
    try:
        AuditEntry.objects.create(
            action=action,
            actor=actor if getattr(actor, "pk", None) else None,
            source=source or "",
            content_type=ContentType.objects.get_for_model(type(obj)),
            object_id=pk if pk is not None else getattr(obj, "pk", None),
            target_label=describe(obj),
            changes=scrub(changes or {}),
        )
    except Exception:  # noqa: BLE001
        # Logged and swallowed. Losing an audit row is bad; failing somebody's
        # save because the trail could not be written is worse. `send_robust`
        # would swallow it in any case, so the log is what makes a broken
        # listener visible rather than silent (§4.7).
        logger.exception("audit could not record %s on %r", action, type(obj).__name__)


def on_written(sender, obj, mode, changes, actor=None, source="", **kwargs):
    """A completed write. `mode` is what makes this two actions, not one."""
    _record(
        "created" if mode == "create" else "updated",
        obj,
        actor=actor,
        source=source,
        changes=changes,
    )


def on_deleted(sender, obj, pk, actor=None, source="", **kwargs):
    """A delete. The pk arrives on the event because the collector cleared it."""
    _record("deleted", obj, pk=pk, actor=actor, source=source)


def on_state_changed(sender, obj, from_state, to_state, actor=None, source="", **kwargs):
    """A transition, recorded as the field change it is.

    `audit` does not import `workflow` to learn what a state is: the signal
    carries two names, and two names are a diff.
    """
    _record(
        "state_changed",
        obj,
        actor=actor,
        source=source,
        changes={"state": (from_state, to_state)},
    )


#: The three subscriptions, with the uid each is registered under. A uid makes
#: connecting idempotent — `ready()` may run twice — and is what `disconnect`
#: has to be given to match.
SUBSCRIPTIONS = (
    (signals.object_written, on_written, "plinta.audit.written"),
    (signals.object_deleted, on_deleted, "plinta.audit.deleted"),
    (signals.state_changed, on_state_changed, "plinta.audit.state_changed"),
)


def connect() -> None:
    """Subscribe. Called from `AppConfig.ready()`.

    `object_writing` is deliberately not subscribed to: a write that has not
    happened is not something that happened, and a trail recording intentions
    would record the ones that failed validation too.
    """
    for signal, receiver, uid in SUBSCRIPTIONS:
        signal.connect(receiver, dispatch_uid=uid)


def disconnect() -> None:
    """Stop recording, without uninstalling the app.

    For a bulk import that would otherwise write a million entries, and for
    the test that shows removing the app removes the auditing. The uid must
    match the one it was connected under, or nothing is removed and it looks
    like it worked.
    """
    for signal, _receiver, uid in SUBSCRIPTIONS:
        signal.disconnect(dispatch_uid=uid)


connect()

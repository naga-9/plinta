"""The five signals, and the only functions that send them.

Core emits; contrib listens. A listener imports the signal from here, never
from whatever emits it, so two packages observing each other's writes create no
dependency between themselves.

Every signal carries the same envelope — ``obj``, ``actor``, ``source`` — so a
listener subscribing to several reads one shape. What differs is the payload
each adds.
"""
from __future__ import annotations

import logging
from typing import Any

from django.dispatch import Signal

logger = logging.getLogger(__name__)

#: Before a write is saved. ``fields`` are the names about to be written.
object_writing = Signal()

#: After a write is saved and its M2M applied. ``changes`` is
#: ``{field: (before, after)}``, computed by the caller that performed the write.
object_written = Signal()

#: After a row is deleted.
object_deleted = Signal()

#: A state machine moved a row. ``from_state`` and ``to_state`` are string
#: codes, so core never references a workflow model.
state_changed = Signal()

#: A comment was posted against any row.
comment_posted = Signal()

ALL = (object_writing, object_written, object_deleted, state_changed, comment_posted)


def _send(signal: Signal, sender: type, **payload: Any) -> None:
    """Send to every receiver, surviving any that raise.

    A failing listener must never fail the write that triggered it, so the
    exception is logged and the remaining receivers still run.
    """
    for receiver, response in signal.send_robust(sender=sender, **payload):
        if isinstance(response, Exception):
            logger.exception(
                "%s listener %s.%s failed",
                getattr(signal, "_plinta_name", "event"),
                getattr(receiver, "__module__", "?"),
                getattr(receiver, "__qualname__", receiver),
                exc_info=response,
            )


def emit_writing(obj, *, mode: str, fields: list[str], actor=None, source: str = "") -> None:
    """Announce a write about to happen. ``mode`` is ``create`` or ``update``."""
    _send(object_writing, type(obj), obj=obj, mode=mode, fields=fields, actor=actor, source=source)


def emit_written(obj, *, mode: str, changes: dict, actor=None, source: str = "") -> None:
    """Announce a completed write and what it changed.

    ``changes`` is ``{field: (before, after)}``; on create, ``before`` is None
    for every entry.
    """
    _send(object_written, type(obj), obj=obj, mode=mode, changes=changes, actor=actor, source=source)


def emit_deleted(obj, *, actor=None, source: str = "") -> None:
    """Announce a deleted row. The instance is passed after deletion, so its
    primary key is already gone from the database."""
    _send(object_deleted, type(obj), obj=obj, actor=actor, source=source)


def emit_state_changed(
    obj,
    *,
    from_state: str | None,
    to_state: str,
    actor=None,
    comment: str = "",
    metadata: dict | None = None,
    source: str = "",
) -> None:
    """Announce a state transition. States are codes, never model instances."""
    _send(
        state_changed,
        type(obj),
        obj=obj,
        from_state=from_state,
        to_state=to_state,
        actor=actor,
        comment=comment,
        metadata=metadata or {},
        source=source,
    )


def emit_comment_posted(
    obj, *, actor=None, body: str = "", metadata: dict | None = None, source: str = ""
) -> None:
    """Announce a comment posted against ``obj``, the row it is attached to."""
    _send(
        comment_posted,
        type(obj),
        obj=obj,
        actor=actor,
        body=body,
        metadata=metadata or {},
        source=source,
    )


def has_listeners(signal: Signal, sender: type | None = None) -> bool:
    """Whether anything would receive this signal.

    Lets a caller skip work that only exists to fill a payload — computing a
    diff costs nothing on an install with no listeners.
    """
    return signal.has_listeners(sender)


for _signal, _name in zip(ALL, ("object_writing", "object_written", "object_deleted",
                                "state_changed", "comment_posted"), strict=True):
    _signal._plinta_name = _name

"""A window in which many writes happen, so listeners can coalesce.

Per-row signals still fire inside a batch. What the batch adds is that a
listener can tell one is in progress, buffer, and flush once at the end —
one digest email instead of five thousand, one bulk insert instead of five
thousand.
"""
from __future__ import annotations

import contextvars
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_current: contextvars.ContextVar["Batch | None"] = contextvars.ContextVar(
    "plinta_events_batch", default=None
)


@dataclass
class Batch:
    """The batch in progress. A listener reads ``source`` and registers a flush."""

    source: str
    _on_exit: list[Callable[[], None]] = field(default_factory=list, repr=False)

    def on_exit(self, fn: Callable[[], None]) -> None:
        """Call ``fn`` once when the batch ends. Registering twice queues twice."""
        self._on_exit.append(fn)


@contextmanager
def batch(source: str = "") -> Iterator[Batch]:
    """Open a batch. Nests: an inner block joins the outer batch.

    Flush callbacks run when the outermost block exits, including on an
    exception — a listener that buffered rows must be told to release them
    either way, or it leaks them into the next batch.
    """
    existing = _current.get()
    if existing is not None:
        yield existing
        return

    current = Batch(source=source)
    token = _current.set(current)
    try:
        yield current
    finally:
        _current.reset(token)
        for fn in current._on_exit:
            try:
                fn()
            except Exception:
                logger.exception("batch flush %r failed", getattr(fn, "__qualname__", fn))


def current_batch() -> Batch | None:
    """The batch in progress, or None. A listener calls this to decide whether
    to act now or buffer."""
    return _current.get()

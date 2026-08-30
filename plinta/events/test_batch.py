"""Batching: per-row signals still fire, listeners get to coalesce."""
import logging
import threading

import pytest

from plinta.events import batch, current_batch, emit_written, object_written


class Book:
    pk = 1


def test_no_batch_by_default():
    assert current_batch() is None


def test_inside_a_batch_a_listener_can_see_it():
    with batch(source="import") as b:
        assert current_batch() is b
        assert b.source == "import"
    assert current_batch() is None


def test_per_row_signals_still_fire_inside_a_batch(listen):
    """One signal, not a second bulk shape every listener must handle forever."""
    rows = []
    listen(object_written, lambda sender, **kw: rows.append(kw["obj"]))

    with batch(source="import"):
        for _ in range(3):
            emit_written(Book(), mode="create", changes={})

    assert len(rows) == 3


def test_a_listener_buffers_and_flushes_once():
    buffered, flushed = [], []

    def handler(obj):
        current = current_batch()
        if current is None:
            flushed.append([obj])          # no batch: act immediately
            return
        if not buffered:
            current.on_exit(lambda: flushed.append(list(buffered)))
        buffered.append(obj)

    with batch(source="import"):
        for _ in range(3):
            handler(Book())
        assert flushed == [], "nothing written yet"

    assert len(flushed) == 1 and len(flushed[0]) == 3


def test_a_listener_ignoring_the_batch_still_behaves(listen):
    """Just slower — correctness never depends on noticing the batch."""
    seen = []
    listen(object_written, lambda sender, **kw: seen.append(kw["obj"]))
    with batch(source="import"):
        emit_written(Book(), mode="create", changes={})
    assert len(seen) == 1


def test_batches_nest_into_one():
    """An inner block joins the outer batch rather than starting a second."""
    calls = []
    with batch(source="outer") as outer:
        outer.on_exit(lambda: calls.append("outer"))
        with batch(source="inner") as inner:
            assert inner is outer, "the inner block joined the outer batch"
            assert inner.source == "outer"
        assert calls == [], "the inner block did not flush"
    assert calls == ["outer"]


def test_flush_runs_when_the_body_raises():
    """A listener holding buffered rows must be released either way."""
    calls = []
    with pytest.raises(RuntimeError):
        with batch(source="import") as b:
            b.on_exit(lambda: calls.append("flushed"))
            raise RuntimeError("import failed halfway")
    assert calls == ["flushed"]
    assert current_batch() is None


def test_a_flush_that_raises_does_not_break_the_others(caplog):
    calls = []
    with caplog.at_level(logging.ERROR):
        with batch() as b:
            b.on_exit(lambda: (_ for _ in ()).throw(RuntimeError("flush failed")))
            b.on_exit(lambda: calls.append("second"))
    assert calls == ["second"]
    assert "flush failed" in caplog.text


def test_flushes_run_in_registration_order():
    calls = []
    with batch() as b:
        b.on_exit(lambda: calls.append(1))
        b.on_exit(lambda: calls.append(2))
    assert calls == [1, 2]


def test_a_batch_does_not_leak_into_another_thread():
    """contextvars, not a module global — a web worker must not see another's."""
    seen = []

    def other_thread():
        seen.append(current_batch())

    with batch(source="import"):
        t = threading.Thread(target=other_thread)
        t.start()
        t.join()

    assert seen == [None]

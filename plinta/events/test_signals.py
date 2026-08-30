"""What each signal carries, and what happens when a listener fails."""
import logging

import pytest

from plinta.events import (
    comment_posted,
    emit_comment_posted,
    emit_deleted,
    emit_state_changed,
    emit_writing,
    emit_written,
    has_listeners,
    object_deleted,
    object_writing,
    object_written,
    state_changed,
)


class Book:
    """Stands in for a consumer's model — the bus never inspects it."""

    def __init__(self, pk=1):
        self.pk = pk


class Sale:
    def __init__(self, pk=1):
        self.pk = pk


@pytest.fixture
def seen():
    """Collect every payload a receiver is handed."""
    captured = []

    def receiver(sender, **kwargs):
        kwargs.pop("signal", None)
        captured.append((sender, kwargs))

    receiver.captured = captured
    return receiver


def test_object_writing_carries_the_fields_about_to_be_written(listen, seen):
    listen(object_writing, seen)
    book = Book()
    emit_writing(book, mode="update", fields=["title", "price"], actor="ada", source="block_edit")

    sender, payload = seen.captured[0]
    assert sender is Book
    assert payload == {
        "obj": book,
        "mode": "update",
        "fields": ["title", "price"],
        "actor": "ada",
        "source": "block_edit",
    }


def test_object_written_carries_the_diff(listen, seen):
    listen(object_written, seen)
    book = Book()
    emit_written(book, mode="update", changes={"price": (9.99, 12.50)}, actor="ada", source="api")

    _, payload = seen.captured[0]
    assert payload["changes"] == {"price": (9.99, 12.50)}
    assert payload["mode"] == "update"


def test_create_uses_the_same_shape_with_no_before(listen, seen):
    """A listener handles one payload shape, not two."""
    listen(object_written, seen)
    emit_written(Book(), mode="create", changes={"title": (None, "Dune")}, source="api")

    _, payload = seen.captured[0]
    assert payload["mode"] == "create"
    assert payload["changes"]["title"][0] is None


def test_object_deleted(listen, seen):
    listen(object_deleted, seen)
    emit_deleted(Book(), actor="ada", source="block_delete")
    _, payload = seen.captured[0]
    assert set(payload) == {"obj", "actor", "source"}


def test_state_changed_carries_codes_not_models(listen, seen):
    """Core never references a Workflow model, so states cross as strings."""
    listen(state_changed, seen)
    emit_state_changed(
        Sale(), from_state="draft", to_state="ordered", actor="ada",
        comment="restock", metadata={"transition": "submit"}, source="workflow",
    )
    _, payload = seen.captured[0]
    assert payload["from_state"] == "draft" and payload["to_state"] == "ordered"
    assert isinstance(payload["metadata"], dict)


def test_state_changed_allows_no_previous_state(listen, seen):
    listen(state_changed, seen)
    emit_state_changed(Sale(), from_state=None, to_state="draft")
    assert seen.captured[0][1]["from_state"] is None


def test_comment_posted_names_its_target(listen, seen):
    listen(comment_posted, seen)
    book = Book()
    emit_comment_posted(book, actor="ada", body="reprint?", source="comment_post")
    _, payload = seen.captured[0]
    assert payload["target"] is book
    assert payload["body"] == "reprint?"


@pytest.mark.parametrize("emit", [
    lambda o: emit_writing(o, mode="create", fields=[]),
    lambda o: emit_written(o, mode="create", changes={}),
    lambda o: emit_deleted(o),
    lambda o: emit_state_changed(o, from_state=None, to_state="x"),
    lambda o: emit_comment_posted(o),
])
def test_every_payload_defaults_its_optional_parts(listen, seen, emit):
    """An event must be emittable from a management command, with no actor."""
    for signal in (object_writing, object_written, object_deleted, state_changed, comment_posted):
        listen(signal, seen)
    emit(Book())
    _, payload = seen.captured[0]
    assert payload.get("actor") is None
    assert payload.get("source") == ""


def test_metadata_defaults_to_a_dict_not_none(listen, seen):
    """So a listener can do metadata['x'] without guarding."""
    listen(state_changed, seen)
    listen(comment_posted, seen)
    emit_state_changed(Sale(), from_state=None, to_state="x")
    emit_comment_posted(Book())
    assert all(p["metadata"] == {} for _, p in seen.captured)


def test_a_receiver_can_filter_by_model(listen, seen):
    """sender is the model class, so a listener need not check obj's type."""
    listen(object_written, seen, sender=Book)
    emit_written(Book(), mode="create", changes={})
    emit_written(Sale(), mode="create", changes={})
    assert len(seen.captured) == 1
    assert seen.captured[0][0] is Book


def test_a_listener_that_raises_does_not_fail_the_write(listen, seen, caplog):
    def explode(sender, **kwargs):
        raise RuntimeError("audit database is down")

    listen(object_written, explode)
    listen(object_written, seen)

    with caplog.at_level(logging.ERROR):
        emit_written(Book(), mode="create", changes={})

    assert len(seen.captured) == 1, "the surviving listener still ran"
    assert "audit database is down" in caplog.text
    assert "object_written" in caplog.text, "the log names the signal"


def test_the_failing_listener_is_named_in_the_log(listen, caplog):
    def broken_handler(sender, **kwargs):
        raise ValueError("nope")

    listen(object_deleted, broken_handler)
    with caplog.at_level(logging.ERROR):
        emit_deleted(Book())
    assert "broken_handler" in caplog.text


def test_emitting_with_no_listeners_is_a_no_op():
    emit_written(Book(), mode="create", changes={})
    emit_deleted(Book())


def test_has_listeners_reports_whether_work_is_worth_doing(listen, seen):
    assert has_listeners(object_written) is False
    listen(object_written, seen)
    assert has_listeners(object_written) is True


def test_has_listeners_respects_the_sender(listen, seen):
    listen(object_written, seen, sender=Book)
    assert has_listeners(object_written, Book) is True
    assert has_listeners(object_written, Sale) is False

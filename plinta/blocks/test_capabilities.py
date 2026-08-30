"""Capabilities: registered by their own app, rendered by a core that knows none."""
import pytest

from plinta.blocks.capabilities import (
    CapabilityError,
    for_object,
    matrix,
    registered,
)
from tests.testapp.models import Book, Region


class Row:
    def __init__(self, pk=1):
        self.pk = pk


# --- registering -----------------------------------------------------------


def test_a_capability_is_registered(capability_registry):
    capability_registry.register_capability("comments", "Comments")
    assert [c.name for c in registered()] == ["comments"]


def test_a_label_defaults_from_the_name(capability_registry):
    cap = capability_registry.register_capability("check_list")
    assert cap.label == "Check List"


def test_a_duplicate_is_refused(capability_registry):
    capability_registry.register_capability("comments")
    with pytest.raises(CapabilityError, match="already registered"):
        capability_registry.register_capability("comments")


@pytest.mark.parametrize("name", ["Comments", "1st", "with-dash", "", "with space"])
def test_an_unusable_name_is_refused(capability_registry, name):
    with pytest.raises(CapabilityError):
        capability_registry.register_capability(name)


def test_order_decides_display(capability_registry):
    capability_registry.register_capability("last", order=200)
    capability_registry.register_capability("first", order=50)
    assert [c.name for c in registered()] == ["first", "last"]


def test_the_same_order_falls_back_to_the_name(capability_registry):
    capability_registry.register_capability("b")
    capability_registry.register_capability("a")
    assert [c.name for c in registered()] == ["a", "b"]


# --- the edit-form probe: does this apply to this row? ---------------------


def test_a_capability_with_no_probe_always_applies(capability_registry):
    capability_registry.register_capability("comments")
    assert [c.name for c in for_object(Row())] == ["comments"]


def test_a_probe_may_refuse_a_row(capability_registry):
    """An unsaved row has nothing to hang a comment on."""
    capability_registry.register_capability(
        "comments", applies_to=lambda obj, **kw: obj.pk is not None
    )
    assert for_object(Row(pk=None)) == []
    assert for_object(Row(pk=1)) != []


def test_a_probe_sees_the_user(capability_registry):
    seen = {}

    def probe(obj, user, **kw):
        seen["user"] = user
        return True

    capability_registry.register_capability("comments", applies_to=probe)
    for_object(Row(), user="ada")
    assert seen["user"] == "ada"


# --- the matrix probe: does this model support it at all? -----------------


def test_a_capability_with_no_probe_supports_every_model(capability_registry):
    capability_registry.register_capability("comments")
    assert [c.name for c in matrix([Book])[Book]] == ["comments"]


def test_a_probe_may_exclude_a_model(capability_registry):
    capability_registry.register_capability(
        "comments", supports=lambda model, **kw: model is Book
    )
    result = matrix([Book, Region])
    assert [c.name for c in result[Book]] == ["comments"]
    assert result[Region] == []


def test_prepare_runs_once_not_once_per_model(capability_registry):
    """Which is what keeps the matrix from issuing a query per model."""
    calls = []

    capability_registry.register_capability(
        "comments",
        prepare=lambda: calls.append(1) or {Book},
        supports=lambda model, state, **kw: model in state,
    )
    result = matrix([Book, Region])
    assert len(calls) == 1
    assert [c.name for c in result[Book]] == ["comments"]
    assert result[Region] == []


def test_the_two_probes_answer_different_questions(capability_registry):
    """A model may support a capability that does not apply to a given row."""
    capability_registry.register_capability(
        "comments",
        supports=lambda model, **kw: True,
        applies_to=lambda obj, **kw: obj.pk is not None,
    )
    assert matrix([Book])[Book] != []
    assert for_object(Row(pk=None)) == []


# --- what core knows -------------------------------------------------------


def test_core_registers_none():
    """An app registers its own. Core renders whatever the registry holds, so
    with no contrib app installed there is nothing to render."""
    assert registered() == []


def test_an_empty_registry_gives_every_model_nothing():
    assert matrix([Book, Region]) == {Book: [], Region: []}

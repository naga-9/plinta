"""What a block's card offers to do with it."""
import pytest

from plinta.blocks.actions import (
    BlockActionError,
    actions_for,
    register_block_action,
    registered,
)


class Block:
    def __init__(self, component_type="table_plinta"):
        self.component_type = component_type


class User:
    def __init__(self, *perms):
        self.perms = set(perms)

    def has_perm(self, codename):
        return codename in self.perms


def test_core_registers_the_view_picker():
    """Through the same door a contrib export button uses: a private path for
    the bundled one would make the door fiction."""
    assert "saved_view" in {a.name for a in registered()}


def test_an_action_with_no_components_applies_to_all(block_action_registry):
    register_block_action("export", template="x.html")
    assert [a.name for a in actions_for(Block("chart_plotly"), User())] == ["export"]


def test_an_action_names_the_components_it_suits(block_action_registry):
    """A column chooser is a table's; offering it on a chart is a button that
    does nothing."""
    register_block_action("columns", template="x.html", components={"table_plinta"})
    assert actions_for(Block("table_plinta"), User())
    assert actions_for(Block("chart_plotly"), User()) == []


def test_a_permission_gates_it(block_action_registry):
    register_block_action("export", template="x.html", permission="app.export_block")
    assert actions_for(Block(), User()) == []
    assert actions_for(Block(), User("app.export_block"))


def test_a_condition_reads_what_the_caller_already_knows(block_action_registry):
    """Passed in rather than looked up: one query per block per action is how
    a dashboard of eight becomes forty round trips."""
    register_block_action("picker", template="x.html", when=lambda views=(), **kw: bool(views))
    assert actions_for(Block(), User(), views=[]) == []
    assert actions_for(Block(), User(), views=["a view"])


def test_a_condition_that_fails_hides_only_itself(block_action_registry):
    """A broken action must not take the card down with it."""
    def boom(**kwargs):
        raise RuntimeError("nope")

    register_block_action("broken", template="x.html", when=boom)
    register_block_action("fine", template="y.html")
    assert [a.name for a in actions_for(Block(), User())] == ["fine"]


def test_order_decides_placement(block_action_registry):
    register_block_action("second", template="x.html", order=20)
    register_block_action("first", template="y.html", order=10)
    assert [a.name for a in actions_for(Block(), User())] == ["first", "second"]


def test_a_name_is_taken_once(block_action_registry):
    register_block_action("export", template="x.html")
    with pytest.raises(BlockActionError, match="already registered"):
        register_block_action("export", template="y.html")


@pytest.mark.parametrize("name", ["Export", "add record", "", "2fa"])
def test_the_name_must_be_an_identifier(block_action_registry, name):
    with pytest.raises(BlockActionError, match="lowercase"):
        register_block_action(name, template="x.html")

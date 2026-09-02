"""Where a component's settings are arranged.

Core owns the mechanisms — the column chooser, the sort builder, the rule
that a blank control means "same as the block". The component owns where they
go, because a chart, a gantt and a table have nothing in common but the
mechanisms and core would arrange all three wrong.
"""
import pytest
from pydantic import BaseModel

from plinta.forms.layouts import (
    DEFAULT,
    LayoutError,
    layout_for,
    register_config_layout,
    registered,
)


class Base(BaseModel):
    columns: list[str] = []


class Derived(Base):
    page_size: int = 25


def test_a_schema_with_no_layout_is_stacked(config_layout_registry):
    """A component that registers nothing still has a settings form."""
    assert layout_for(Derived) == DEFAULT


def test_a_registered_layout_is_found(config_layout_registry):
    register_config_layout(Derived, "app/chart.html")
    assert layout_for(Derived) == "app/chart.html"


def test_a_base_schemas_layout_reaches_a_subclass(config_layout_registry):
    """The same rule widget overrides follow: a setting declared on a base is
    the same setting on every subclass."""
    register_config_layout(Base, "app/base.html")
    assert layout_for(Derived) == "app/base.html"


def test_a_subclass_may_arrange_it_differently(config_layout_registry):
    register_config_layout(Base, "app/base.html")
    register_config_layout(Derived, "app/derived.html")
    assert layout_for(Derived) == "app/derived.html"
    assert layout_for(Base) == "app/base.html"


def test_a_schema_is_arranged_once(config_layout_registry):
    register_config_layout(Derived, "app/one.html")
    with pytest.raises(LayoutError, match="already has"):
        register_config_layout(Derived, "app/two.html")


def test_a_layout_names_a_template(config_layout_registry):
    with pytest.raises(LayoutError, match="names no template"):
        register_config_layout(Derived, "")


def test_registered_lists_the_schemas(config_layout_registry):
    register_config_layout(Derived, "app/chart.html")
    assert registered() == ["Derived"]

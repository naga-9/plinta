"""Registering a bespoke widget for one field of one schema."""
from typing import Any, Optional

import pytest
from pydantic import BaseModel, Field

from plinta.forms.fields import fields_for
from plinta.forms.overrides import OverrideError, overrides_for, register_widget


class Config(BaseModel):
    title: str = "Untitled"
    page_size: int = 25
    enable_create: bool = False
    ratio: float = 1.0
    height: Optional[int] = None
    series: list[dict[str, Any]] = Field(
        default_factory=list, description="one entry per plotted series"
    )


class OtherConfig(BaseModel):
    series: list[dict[str, Any]] = Field(default_factory=list)


def test_register_widget_is_per_schema_and_field(override_registry):
    override_registry.register_widget(Config, "series", "chart/series.html")
    override_registry.register_widget(OtherConfig, "series", "gauge/series.html")
    assert override_registry.overrides_for(Config) == {"series": "chart/series.html"}
    assert override_registry.overrides_for(OtherConfig) == {"series": "gauge/series.html"}


def test_a_second_override_on_one_field_is_refused(override_registry):
    override_registry.register_widget(Config, "series", "a.html")
    with pytest.raises(OverrideError, match="already has"):
        override_registry.register_widget(Config, "series", "b.html")


def test_a_field_that_does_not_exist_is_refused(override_registry):
    """A typo would otherwise register an override that can never fire."""
    with pytest.raises(OverrideError, match="no field 'sereis'"):
        override_registry.register_widget(Config, "sereis", "chart/series.html")


def test_a_schema_with_no_overrides_gets_an_empty_map(override_registry):
    assert override_registry.overrides_for(OtherConfig) == {}


def test_overrides_feed_straight_into_fields_for(override_registry):
    override_registry.register_widget(Config, "series", "chart/series.html")
    fields = {f.name: f for f in fields_for(Config, overrides=override_registry.overrides_for(Config))}
    assert fields["series"].override_template == "chart/series.html"


# --- inheritance ------------------------------------------------------------


def test_a_base_schemas_override_reaches_a_subclass(widget_registry):
    """`columns` is declared on `ComponentConfig`, so a chooser registered for
    it must reach every component's config — otherwise each author registers
    the same widget and one of them forgets."""
    class Base(BaseModel):
        columns: list[str] = []

    class Derived(Base):
        page_size: int = 50

    register_widget(Base, "columns", "base/columns.html")
    assert overrides_for(Derived) == {"columns": "base/columns.html"}


def test_a_subclass_may_override_the_override(widget_registry):
    class Base(BaseModel):
        columns: list[str] = []

    class Derived(Base):
        pass

    register_widget(Base, "columns", "base/columns.html")
    register_widget(Derived, "columns", "derived/columns.html")
    assert overrides_for(Derived) == {"columns": "derived/columns.html"}
    assert overrides_for(Base) == {"columns": "base/columns.html"}

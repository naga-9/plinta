"""Deriving a form from a schema, coercing it back, and the override registry."""
from typing import Any, Optional

import pytest
from pydantic import BaseModel, Field

from plinta.forms.fields import fields_for, unwrap_optional, widget_for
from plinta.forms.overrides import OverrideError
from plinta.forms.parse import ABSENT, coerce, parse


class Config(BaseModel):
    title: str = "Untitled"
    page_size: int = 25
    enable_create: bool = False
    ratio: float = 1.0
    height: Optional[int] = None
    series: list[dict[str, Any]] = Field(
        default_factory=list, description="one entry per plotted series"
    )


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (bool, "bool"),
        (int, "number"),
        (float, "number"),
        (str, "text"),
        (Optional[int], "number"),
        (int | None, "number"),
        (list[str], "json"),
        (dict[str, Any], "json"),
        (list[dict[str, Any]], "json"),
        (set[int], "json"),
        (Config, "json"),
        (Any, "text"),
        (int | str, "text"),
    ],
)
def test_widget_for(annotation, expected):
    assert widget_for(annotation) == expected


def test_optional_is_unwrapped_for_the_widget_but_a_union_is_not():
    assert unwrap_optional(Optional[int]) is int
    assert unwrap_optional(int | str) == int | str


def test_fields_are_derived_in_declaration_order():
    assert [f.name for f in fields_for(Config)] == [
        "title",
        "page_size",
        "enable_create",
        "ratio",
        "height",
        "series",
    ]


def test_a_field_carries_its_default_and_description():
    series = {f.name: f for f in fields_for(Config)}["series"]
    assert series.widget == "json"
    assert series.default == [], "default_factory is called, not reported as a factory"
    assert series.description == "one entry per plotted series"


def test_required_is_reported():
    class Required(BaseModel):
        name: str

    assert fields_for(Required)[0].required is True
    assert fields_for(Config)[0].required is False


def test_editable_defaults_to_everything():
    assert all(f.editable for f in fields_for(Config))


def test_editable_narrows_without_dropping_fields():
    """A read-only field is still shown; the caller decides, not this layer."""
    fields = {f.name: f for f in fields_for(Config, editable={"title"})}
    assert len(fields) == 6
    assert fields["title"].editable and not fields["page_size"].editable


def test_an_override_replaces_the_derived_widget():
    fields = {f.name: f for f in fields_for(Config, overrides={"series": "chart/series.html"})}
    assert fields["series"].override_template == "chart/series.html"
    assert fields["series"].widget == "json", "the derived widget stays as the fallback"
    assert fields["title"].override_template is None


@pytest.mark.parametrize(
    ("raw", "annotation", "expected"),
    [
        # Scalars pass straight through: pydantic coerces these itself, and a
        # second coercion here would be a second contract.
        ("true", bool, "true"),
        ("on", bool, "on"),
        ("25", int, "25"),
        ("1.5", float, "1.5"),
        ("hello", str, "hello"),
        # A container arrives as a JSON string, which pydantic will not parse.
        ("[1, 2]", list[int], [1, 2]),
        ('{"a": 1}', dict[str, int], {"a": 1}),
        # Cleared fields.
        ("", str, ""),
        ("", Optional[int], None),
        ("", int, ABSENT),
        ("", bool, ABSENT),
        (None, Optional[str], None),
    ],
)
def test_coerce(raw, annotation, expected):
    assert coerce(raw, annotation) == expected


def test_scalars_are_left_to_pydantic_and_it_gets_them_right():
    """The coercion coerce() no longer does still has to happen."""
    config, errors = parse(Config, {"page_size": "50", "enable_create": "on", "ratio": "1.5"})
    assert errors is None
    assert config["page_size"] == 50
    assert config["enable_create"] is True
    assert config["ratio"] == 1.5


def test_a_cleared_required_field_takes_the_schema_default():
    config, errors = parse(Config, {"page_size": ""})
    assert errors is None and config["page_size"] == 25


def test_uncoercible_input_is_left_for_the_schema_to_reject():
    """Silently substituting a default would store something nobody submitted."""
    assert coerce("abc", int) == "abc"
    assert coerce("{not json", list[int]) == "{not json"


def test_parse_returns_a_stored_dict():
    config, errors = parse(Config, {"title": "Sales", "page_size": "50"})
    assert errors is None
    assert config["title"] == "Sales" and config["page_size"] == 50


def test_absent_fields_take_the_schema_default():
    config, _ = parse(Config, {"title": "Sales"})
    assert config["page_size"] == 25


def test_errors_are_keyed_by_field():
    config, errors = parse(Config, {"page_size": "abc"})
    assert config is None
    assert "page_size" in errors


def test_a_non_editable_field_is_ignored_even_when_submitted():
    config, _ = parse(Config, {"title": "Sales", "page_size": "999"}, editable={"title"})
    assert config["title"] == "Sales"
    assert config["page_size"] == 25, "the submitted value was discarded"


def test_a_json_field_round_trips():
    config, errors = parse(Config, {"series": '[{"field": "qty"}]'})
    assert errors is None and config["series"] == [{"field": "qty"}]


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

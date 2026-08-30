"""Turning submitted values back into a validated dict."""
from typing import Any, Optional

import pytest
from pydantic import BaseModel, Field

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

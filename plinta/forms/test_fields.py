"""Deriving form fields from a pydantic schema."""
from typing import Any, Optional

import pytest
from pydantic import BaseModel, Field

from plinta.forms.fields import fields_for, unwrap_optional, widget_for


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

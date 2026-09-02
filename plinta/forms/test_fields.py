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


# --- closed sets ------------------------------------------------------------


def test_a_literal_is_a_choice():
    """Rendered as text, a form offers every string and validation refuses
    all but three — so the writer finds the answer by being wrong."""
    from typing import Literal

    class Config(BaseModel):
        chart_type: Literal["line", "bar", "area"] = "line"

    field = fields_for(Config)[0]
    assert field.widget == "choice"
    assert field.choices == ("line", "bar", "area")


def test_an_enum_is_a_choice():
    import enum

    class Kind(str, enum.Enum):
        LINE = "line"
        BAR = "bar"

    class Config(BaseModel):
        kind: Kind = Kind.LINE

    field = fields_for(Config)[0]
    assert field.widget == "choice"
    assert field.choices == ("line", "bar")


def test_an_optional_literal_is_still_a_choice():
    from typing import Literal, Optional  # noqa: F401

    class Config(BaseModel):
        chart_type: "Optional[Literal['line', 'bar']]" = None

    assert fields_for(Config)[0].widget == "choice"


def test_an_ordinary_string_is_not():
    class Config(BaseModel):
        title: str = ""

    field = fields_for(Config)[0]
    assert field.widget == "text"
    assert field.choices == ()


# --- a setting that names a column ------------------------------------------


def test_a_field_may_ask_for_a_mechanism_by_name():
    """`total_field="sale_total"` is a string to the type system and a choice
    to a person. Derived from `str` it is a text box, and whatever is typed
    passes validation and fails at the query."""
    from pydantic import Field as PydanticField

    class Config(BaseModel):
        total_field: str = PydanticField(
            default="", json_schema_extra={"widget": "column"}
        )

    assert fields_for(Config)[0].widget == "column"


def test_a_declared_widget_beats_the_derived_one():
    from pydantic import Field as PydanticField

    class Config(BaseModel):
        count: int = PydanticField(default=0, json_schema_extra={"widget": "column"})

    assert fields_for(Config)[0].widget == "column"


def test_a_field_that_asks_for_nothing_still_derives():
    class Config(BaseModel):
        title: str = ""

    assert fields_for(Config)[0].widget == "text"

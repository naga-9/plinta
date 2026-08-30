"""A column drawn by a registered renderer, and the joins that costs."""
import pytest
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils.html import format_html

from plinta.datasources import prefetch
from plinta.datasources.models import DataSource, DataSourceField
from plinta.renderers.fields import (
    FieldRendererError,
    get_field_renderer,
    is_field_renderer,
    joins_for,
    render_field,
)
from tests.testapp.models import Book, Region


class Field:
    """The parts of a DataSourceField a renderer reads."""

    def __init__(self, renderer="", format="", decimals=None, prefix="", suffix=""):
        self.renderer = renderer
        self.format = format
        self.decimals = decimals
        self.prefix = prefix
        self.suffix = suffix
        self.thousands_separator = False


def nothing(value, **kw):
    return ""


# --- registering -----------------------------------------------------------


def test_registers_as_a_decorator(field_renderer_registry):
    @field_renderer_registry.register_field_renderer("shout")
    def shout(value, **kw):
        return str(value).upper()

    assert is_field_renderer("shout")
    assert get_field_renderer("shout").render is shout


def test_a_duplicate_is_refused(field_renderer_registry):
    field_renderer_registry.register_field_renderer("shout")(nothing)
    with pytest.raises(FieldRendererError, match="already registered"):
        field_renderer_registry.register_field_renderer("shout")(nothing)


@pytest.mark.parametrize("name", ["Shout", "1st", "with-dash", "", "with space"])
def test_an_unusable_name_is_refused(field_renderer_registry, name):
    with pytest.raises(FieldRendererError):
        field_renderer_registry.register_field_renderer(name)(nothing)


def test_an_unregistered_name_fails_loudly(field_renderer_registry):
    with pytest.raises(FieldRendererError, match="no field renderer named"):
        get_field_renderer("nonesuch")


def test_the_error_lists_what_is_registered(field_renderer_registry):
    field_renderer_registry.register_field_renderer("shout")(nothing)
    with pytest.raises(FieldRendererError, match="registered: shout"):
        get_field_renderer("other")


# --- drawing ---------------------------------------------------------------


def test_a_column_naming_a_renderer_uses_it(field_renderer_registry):
    field_renderer_registry.register_field_renderer("shout")(
        lambda value, **kw: str(value).upper()
    )
    assert render_field("dune", Field(renderer="shout")) == "DUNE"


def test_a_column_naming_none_is_formatted(field_renderer_registry):
    """A caller never asks whether a column has a renderer."""
    from decimal import Decimal

    assert render_field(Decimal("5"), Field(decimals=2, prefix="$")) == "$5.00"


def test_no_column_at_all_is_formatted(field_renderer_registry):
    assert render_field(5) == "5"


def test_a_renderer_may_take_only_what_it_uses(field_renderer_registry):
    """Called with keywords, so a renderer ignoring the row is legal."""
    field_renderer_registry.register_field_renderer("plain")(
        lambda value, **kw: str(value)
    )
    assert render_field(5, Field(renderer="plain")) == "5"


def test_a_renderer_sees_the_row_and_the_user(field_renderer_registry):
    seen = {}

    @field_renderer_registry.register_field_renderer("spy")
    def spy(value, *, obj, field, user):
        seen.update(value=value, obj=obj, field=field, user=user)
        return ""

    field = Field(renderer="spy")
    render_field("v", field, obj="row", user="ada")
    assert seen == {"value": "v", "obj": "row", "field": field, "user": "ada"}


def test_a_renderer_may_return_markup(field_renderer_registry):
    field_renderer_registry.register_field_renderer("chip")(
        lambda value, **kw: format_html("<span>{}</span>", value)
    )
    assert render_field("new", Field(renderer="chip")) == "<span>new</span>"


def test_a_column_naming_an_unregistered_renderer_raises(field_renderer_registry):
    with pytest.raises(FieldRendererError):
        render_field("x", Field(renderer="gone"))


# --- the joins it declares -------------------------------------------------


def test_a_renderer_declaring_nothing_needs_nothing(field_renderer_registry):
    field_renderer_registry.register_field_renderer("plain")(nothing)
    assert joins_for([Field(renderer="plain")]) == (set(), set())


def test_a_declared_select_related_is_collected(field_renderer_registry):
    field_renderer_registry.register_field_renderer("r", select_related=["region"])(nothing)
    assert joins_for([Field(renderer="r")]) == ({"region"}, set())


def test_a_declared_prefetch_is_collected(field_renderer_registry):
    field_renderer_registry.register_field_renderer("r", prefetch_related=["watchers"])(
        nothing
    )
    assert joins_for([Field(renderer="r")]) == (set(), {"watchers"})


def test_several_columns_combine(field_renderer_registry):
    field_renderer_registry.register_field_renderer("a", select_related=["region"])(nothing)
    field_renderer_registry.register_field_renderer(
        "b", select_related=["owner"], prefetch_related=["watchers"]
    )(nothing)
    assert joins_for([Field(renderer="a"), Field(renderer="b")]) == (
        {"region", "owner"},
        {"watchers"},
    )


def test_a_column_without_a_renderer_is_skipped(field_renderer_registry):
    assert joins_for([Field()]) == (set(), set())


def test_an_unregistered_renderer_contributes_no_joins(field_renderer_registry):
    """Reported by the boot check; a query is not the place to raise."""
    assert joins_for([Field(renderer="gone")]) == (set(), set())


# --- the point of declaring them -------------------------------------------


@pytest.mark.django_db
def test_a_declared_join_removes_the_query_per_row(
    field_renderer_registry, django_assert_num_queries
):
    """The case derivation cannot see: the column is `title`, and the renderer
    reads `region`."""
    ada = User.objects.create(username="ada")
    north = Region.objects.create(name="North")
    for title in ("Dune", "Emma", "Ulysses"):
        Book.objects.create(title=title, owner=ada, region=north)

    field_renderer_registry.register_field_renderer("titled", select_related=["region"])(
        lambda value, *, obj, **kw: f"{value} ({obj.region.name})"
    )

    ds = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    column = DataSourceField.objects.create(
        data_source=ds, field_name="title", label="Title", renderer="titled"
    )
    select, prefetched = joins_for([column])

    rows = prefetch.apply(
        Book.objects.all(), ["title"], extra_select=select, extra_prefetch=prefetched
    )
    with django_assert_num_queries(1):
        assert [render_field(b.title, column, obj=b) for b in rows] == [
            "Dune (North)",
            "Emma (North)",
            "Ulysses (North)",
        ]

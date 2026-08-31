"""Rows as a table, and what is escaped on the way."""
from decimal import Decimal

import pytest
from django.utils.safestring import SafeString

from plinta.renderers.html import HtmlRenderer, cell, value_of


class Field:
    def __init__(self, field_name, label="", renderer="", format="", **display):
        self.field_name = field_name
        self.label = label or field_name
        self.renderer = renderer
        self.format = format
        self.decimals = display.get("decimals")
        self.prefix = display.get("prefix", "")
        self.suffix = display.get("suffix", "")
        self.thousands_separator = display.get("thousands_separator", False)


class Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def render(rows, fields, user=None):
    return HtmlRenderer().render(rows, fields, {}, user)


# --- reading a value -------------------------------------------------------


def test_a_plain_attribute():
    assert value_of(Row(title="Dune"), "title") == "Dune"


def test_a_traversed_path():
    assert value_of(Row(region=Row(name="North")), "region__name") == "North"


def test_a_null_relation_is_an_empty_cell():
    """Not an AttributeError one row into the page."""
    assert value_of(Row(region=None), "region__name") is None


def test_a_missing_attribute_is_none():
    assert value_of(Row(), "nonesuch") is None


def test_a_choices_field_shows_its_label():
    """A column showing `placed` where the model says "Placed" is showing the
    database's answer to a question the reader asked of the application."""
    row = Row(status="placed", get_status_display=lambda: "Placed")
    assert value_of(row, "status") == "Placed"


def test_a_choices_field_across_a_relation_shows_its_label():
    order = Row(status="placed", get_status_display=lambda: "Placed")
    assert value_of(Row(order=order), "order__status") == "Placed"


def test_a_plain_field_is_unaffected():
    assert value_of(Row(title="Dune"), "title") == "Dune"


# --- a cell ----------------------------------------------------------------


def test_a_value_is_formatted():
    field = Field("price", decimals=2, prefix="$")
    assert cell(Row(price=Decimal("5")), field) == "$5.00"


def test_a_null_is_empty():
    assert cell(Row(title=None), Field("title")) == ""


def test_a_consumers_data_is_escaped():
    """A cell is escaped here, not by whoever inserts it."""
    row = Row(title="<script>alert(1)</script>")
    assert "<script>" not in cell(row, Field("title"))
    assert "&lt;script&gt;" in cell(row, Field("title"))


def test_a_cell_is_safe_to_insert():
    assert isinstance(cell(Row(title="Dune"), Field("title")), SafeString)


def test_an_escaped_cell_is_not_escaped_twice():
    out = render([Row(title="a & b")], [Field("title")])
    assert "a &amp; b" in out
    assert "&amp;amp;" not in out


def test_an_html_column_is_not_escaped(field_renderer_registry):
    """Rich text a consumer stored as markup, declared as such."""
    row = Row(body="<b>bold</b>")
    assert cell(row, Field("body", format="html")) == "<b>bold</b>"


def test_a_field_renderer_may_emit_markup(field_renderer_registry):
    field_renderer_registry.register_field_renderer("chip")(
        lambda value, **kw: f"<span>{value}</span>"
    )
    row = Row(state="new")
    assert cell(row, Field("state", renderer="chip")) == "<span>new</span>"


def test_a_field_renderer_sees_the_whole_row(field_renderer_registry):
    field_renderer_registry.register_field_renderer("both")(
        lambda value, *, obj, **kw: f"{value}/{obj.region}"
    )
    row = Row(title="Dune", region="North")
    assert cell(row, Field("title", renderer="both")) == "Dune/North"


def test_a_field_renderer_sees_the_user(field_renderer_registry):
    field_renderer_registry.register_field_renderer("mine")(
        lambda value, *, user, **kw: f"{value} for {user}"
    )
    assert cell(Row(title="Dune"), Field("title", renderer="mine"), "ada") == "Dune for ada"


# --- the table -------------------------------------------------------------


def test_a_header_per_column():
    out = render([], [Field("title", "Title"), Field("price", "Price")])
    assert "<th>Title</th><th>Price</th>" in out


def test_a_row_per_object():
    rows = [Row(title="Dune"), Row(title="Emma")]
    out = render(rows, [Field("title")])
    assert out.count("<tr>") == 3  # one header, two body


def test_a_cell_per_column():
    out = render([Row(title="Dune", pages=412)], [Field("title"), Field("pages")])
    assert "<td>Dune</td><td>412</td>" in out


def test_no_rows_says_so():
    """An empty table body reads as broken; one that says so reads as a filter
    that matched nothing, which is what it usually is."""
    out = render([], [Field("title", "Title")])
    assert "No records" in out


def test_the_empty_row_spans_every_column():
    out = render([], [Field("title"), Field("pages")])
    assert 'colspan="2"' in out


def test_a_block_may_word_the_empty_state_itself():
    out = HtmlRenderer().render([], [Field("title")], {"empty_text": "No books yet"}, None)
    assert "No books yet" in out
    assert "No records" not in out


def test_an_empty_state_is_escaped():
    out = HtmlRenderer().render([], [Field("title")], {"empty_text": "<b>none</b>"}, None)
    assert "<b>none</b>" not in out


def test_no_columns_is_an_empty_header():
    out = render([Row(title="Dune")], [])
    assert "<thead><tr></tr></thead>" in out


def test_the_output_is_safe_to_insert():
    assert isinstance(render([], [Field("title")]), SafeString)


def test_a_column_label_is_escaped():
    """A label is configuration, and configuration is written by people."""
    out = render([], [Field("title", "<b>Title</b>")])
    assert "<b>Title</b>" not in out


@pytest.mark.django_db
def test_the_renderer_asks_no_questions_of_the_database(django_assert_num_queries):
    """It draws what it was handed; it cannot fetch what it was not given."""
    rows = [Row(title="Dune"), Row(title="Emma")]
    with django_assert_num_queries(0):
        render(rows, [Field("title")])


def test_it_renders_only_the_fields_it_was_given():
    """Field permission narrowed them upstream; the renderer cannot widen it."""
    row = Row(title="Dune", secret="hidden")
    assert "hidden" not in render([row], [Field("title")])


@pytest.mark.parametrize("value,expected", [(True, "Yes"), (False, "No"), (0, "0")])
def test_values_go_through_the_shared_formatter(value, expected):
    assert f"<td>{expected}</td>" in render([Row(v=value)], [Field("v")])


# --- appearance, chosen per block -------------------------------------------


def test_a_plain_table_carries_only_its_base_class():
    html = HtmlRenderer().render([], [Field("title")], {}, None)
    assert 'class="pl-table"' in html


@pytest.mark.parametrize(
    "flag,expected",
    [
        ("striped", "pl-table--striped"),
        ("compact", "pl-table--compact"),
        ("bordered", "pl-table--bordered"),
    ],
)
def test_each_flag_adds_its_modifier(flag, expected):
    html = HtmlRenderer().render([], [Field("title")], {flag: True}, None)
    assert f'class="pl-table {expected}"' in html


def test_the_order_is_fixed_not_the_config_s():
    """A diff of two blocks should show what differs, not how it was typed."""
    one = HtmlRenderer().render([], [Field("title")], {"bordered": True, "striped": True}, None)
    two = HtmlRenderer().render([], [Field("title")], {"striped": True, "bordered": True}, None)
    assert 'class="pl-table pl-table--striped pl-table--bordered"' in one
    assert one == two


def test_a_false_flag_adds_nothing():
    html = HtmlRenderer().render([], [Field("title")], {"striped": False}, None)
    assert "pl-table--striped" not in html


def test_a_style_pack_renames_them(settings, style_registry):
    """They are vocabulary, so Bootstrap's own names arrive by mapping."""
    from plinta.utils.styles import register_style_pack

    register_style_pack("acme", {"table": "t", "table_striped": "t-zebra"})
    settings.PLINTA_STYLE_PACK = "acme"
    html = HtmlRenderer().render([], [Field("title")], {"striped": True}, None)
    assert 'class="t t-zebra"' in html

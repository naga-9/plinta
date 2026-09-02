"""The component contract's own helpers."""
from plinta.components.base import ColumnsConfig, ComponentConfig, choose_columns


# --- the default column set -------------------------------------------------


class Column:
    def __init__(self, field_name, visible=True):
        self.field_name = field_name
        self.visible = visible


def test_an_invisible_column_is_not_in_the_default_set():
    """`visible` is 'shown by default', and was read nowhere: a column with it
    unticked appeared anyway."""
    permitted = [Column("title"), Column("internal_note", visible=False)]
    chosen = choose_columns(permitted, ComponentConfig())
    assert [c.field_name for c in chosen] == ["title"]


def test_naming_a_column_overrides_the_default():
    """The flag decides the default set; the permission decides what may be
    seen. So a saved view may ask for a column left out of the default."""
    permitted = [Column("title"), Column("internal_note", visible=False)]
    chosen = choose_columns(permitted, ColumnsConfig(columns=["internal_note"]))
    assert [c.field_name for c in chosen] == ["internal_note"]


def test_a_column_the_viewer_may_not_see_stays_out():
    """Naming it cannot widen: `permitted` is the whole universe."""
    permitted = [Column("title")]
    chosen = choose_columns(permitted, ColumnsConfig(columns=["salary", "title"]))
    assert [c.field_name for c in chosen] == ["title"]


def test_a_component_that_draws_no_columns_has_no_column_setting():
    """A KPI reads one aggregate and a gauge one number: neither has columns
    to choose between, and a chooser on their card was a control for a
    setting that meant nothing."""
    assert "columns" not in ComponentConfig.model_fields
    assert "columns" in ColumnsConfig.model_fields


def test_a_config_without_columns_still_draws_every_permitted_one():
    """`choose_columns` asks, and takes the default set when there is no
    answer — so a KPI reads what it may read."""
    permitted = [Column("title"), Column("author")]
    chosen = choose_columns(permitted, ComponentConfig())
    assert [c.field_name for c in chosen] == ["title", "author"]

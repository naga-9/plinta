"""The component contract's own helpers."""
from plinta.components.base import ComponentConfig, choose_columns


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
    chosen = choose_columns(permitted, ComponentConfig(columns=["internal_note"]))
    assert [c.field_name for c in chosen] == ["internal_note"]


def test_a_column_the_viewer_may_not_see_stays_out():
    """Naming it cannot widen: `permitted` is the whole universe."""
    permitted = [Column("title")]
    chosen = choose_columns(permitted, ComponentConfig(columns=["salary", "title"]))
    assert [c.field_name for c in chosen] == ["title"]

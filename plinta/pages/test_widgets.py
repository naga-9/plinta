"""Filter widgets: a registry, not a closed enum."""
import pytest

from plinta.pages.widgets import (
    WidgetError,
    find,
    get,
    register_filter_widget,
    registered,
)


def test_core_registers_its_five():
    assert set(registered()) >= {
        "input_plinta", "boolean_plinta", "select_plinta", "multiselect_plinta", "daterange_plinta"
    }


def test_only_multiselect_takes_several_values():
    assert get("multiselect_plinta").multiple is True
    assert get("select_plinta").multiple is False
    assert get("input_plinta").multiple is False


def test_only_the_choosers_want_options():
    """Calling `options_for` for a text input would query for a list nothing
    draws."""
    assert get("select_plinta").needs_options is True
    assert get("multiselect_plinta").needs_options is True
    assert get("input_plinta").needs_options is False
    assert get("daterange_plinta").needs_options is False


def test_a_third_party_can_add_one(widget_registry):
    """The whole reason this is a registry: a closed enum in core meant a
    consumer who installed a fetching multi-select could not choose it."""
    register_filter_widget(
        "multiselect_tomselect",
        template="plinta/tomselect/multi.html",
        multiple=True,
        needs_options=True,
    )
    assert get("multiselect_tomselect").multiple is True


def test_an_unknown_name_finds_nothing_rather_than_raising(widget_registry):
    """A filter naming an uninstalled widget must still draw."""
    assert find("multiselect_tomselect") is None


def test_asking_for_one_by_name_raises_and_says_what_exists(widget_registry):
    register_filter_widget("input_plinta", template="x.html")
    with pytest.raises(WidgetError, match="registered: input"):
        get("nope")


def test_a_name_is_taken_once(widget_registry):
    register_filter_widget("thing", template="x.html")
    with pytest.raises(WidgetError, match="already registered"):
        register_filter_widget("thing", template="y.html")


@pytest.mark.parametrize("name", ["Select", "multi select", "", "2select"])
def test_the_name_must_be_an_identifier(widget_registry, name):
    with pytest.raises(WidgetError, match="lowercase"):
        register_filter_widget(name, template="x.html")

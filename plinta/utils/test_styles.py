"""Style packs: what a pack may rename, and what happens when it lies."""
import pytest

from plinta.utils import styles
from plinta.utils.styles import DEFAULT, StyleError, classes, register_style_pack


def test_the_default_pack_is_plintas_own():
    assert classes()["btn"] == "pl-btn"
    assert classes()["table"] == "pl-table"


def test_a_pack_lists_only_what_it_changes(style_registry):
    """Merged over the default, so restyling buttons is four lines."""
    register_style_pack("minimal", {"btn": "button"})
    pack = classes("minimal")
    assert pack["btn"] == "button"
    assert pack["table"] == DEFAULT["table"]
    assert set(pack) == set(DEFAULT)


def test_an_unknown_class_is_refused(style_registry):
    """A typo would silently leave our own class, which reads as 'not installed'."""
    with pytest.raises(StyleError, match="do not exist: buton"):
        register_style_pack("typo", {"buton": "btn"})


def test_a_name_is_taken_once(style_registry):
    register_style_pack("once", {})
    with pytest.raises(StyleError, match="already registered"):
        register_style_pack("once", {})


@pytest.mark.parametrize("name", ["Bootstrap5", "bs 5", "", "5bs"])
def test_the_name_must_be_an_identifier(style_registry, name):
    with pytest.raises(StyleError, match="lowercase"):
        register_style_pack(name, {})


def test_an_unregistered_pack_raises_rather_than_falling_back(settings, style_registry):
    """Falling back would draw plinta's classes against a stylesheet that does
    not define them — a broken-looking screen with nothing to explain it."""
    settings.PLINTA_STYLE_PACK = "nope"
    with pytest.raises(StyleError, match="no style pack named 'nope'"):
        classes()


def test_the_setting_selects_the_pack(settings, style_registry):
    register_style_pack("brand", {"btn": "b-button"})
    settings.PLINTA_STYLE_PACK = "brand"
    assert classes()["btn"] == "b-button"


def test_every_key_is_a_string(style_registry):
    """The templates interpolate these straight into `class=`."""
    assert all(isinstance(v, str) for v in DEFAULT.values())


def test_plinta_cannot_be_replaced(style_registry):
    """Our own pack is what every default resolves to."""
    assert styles.PLINTA in styles.registered()
    with pytest.raises(StyleError, match="already registered"):
        register_style_pack(styles.PLINTA, {})

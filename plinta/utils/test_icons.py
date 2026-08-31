"""Icon sets: core's own, and a consumer's beside it."""
import pytest
from django.utils.html import format_html

from plinta.design.icons import ICONS
from plinta.utils.icons import (
    IconError,
    register_defaults,
    register_icon_set,
    registered,
    render,
    split,
)


@pytest.fixture(autouse=True)
def _core(icon_registry):
    register_defaults()


def test_core_registers_through_the_same_door():
    """A private path for the bundled set would make the door fiction."""
    assert registered() == ["plinta"]


@pytest.mark.parametrize(
    "stored,expected",
    [
        ("home", ("plinta", "home")),
        ("plinta:home", ("plinta", "home")),
        ("bi:house", ("bi", "house")),
        ("  bi : house  ", ("bi", "house")),
        ("", ("plinta", "")),
    ],
)
def test_an_unprefixed_name_is_ours(stored, expected):
    """So a short name stays short, and a row written before this keeps
    working."""
    assert split(stored) == expected


def test_core_draws_inline_svg():
    out = render("home")
    assert out.startswith('<svg class="pl-icon"')
    assert 'stroke="currentColor"' in out
    assert "<path" in out


def test_the_colour_is_inherited_not_set():
    """One icon, both themes, no rule per icon."""
    assert "fill=\"none\"" in render("home")
    assert "#" not in render("home")


def test_it_is_hidden_from_a_screen_reader():
    """Decoration beside a label that already says what the thing is."""
    assert 'aria-hidden="true"' in render("home")
    assert 'focusable="false"' in render("home")


def test_the_size_is_the_callers():
    assert 'width="14" height="14"' in render("home", size=14)


@pytest.mark.parametrize("stored", ["", "nonesuch", "fa:house", "plinta:nope"])
def test_anything_unknown_draws_nothing(stored):
    """A gap, not a broken box."""
    assert render(stored) == ""


def test_a_consumer_set_is_used_when_named():
    register_icon_set(
        "bi", render=lambda name, **kw: format_html('<i class="bi bi-{}"></i>', name)
    )
    assert render("bi:house") == '<i class="bi bi-house"></i>'
    assert render("home").startswith("<svg")


def test_a_name_is_taken_once():
    with pytest.raises(IconError, match="already registered"):
        register_icon_set("plinta", render=lambda name, **kw: "")


@pytest.mark.parametrize("name", ["BI", "bootstrap icons", "", "2fa"])
def test_the_set_name_must_be_an_identifier(name):
    with pytest.raises(IconError, match="lowercase"):
        register_icon_set(name, render=lambda n, **kw: "")


def test_the_shipped_icons_are_wrapper_free():
    """The wrapper lives once in the renderer, not 33 times in the data."""
    assert ICONS
    assert not any("<svg" in inner for inner in ICONS.values())
    assert not any("stroke-width" in inner for inner in ICONS.values())


def test_every_shipped_icon_renders():
    assert all(render(name).startswith("<svg") for name in ICONS)

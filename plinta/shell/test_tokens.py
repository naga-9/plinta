"""Generating the theme, and refusing a colour that escaped the token file."""
import json

import pytest

from plinta.shell import tokens
from plinta.shell.management.commands.lint_hex_colors import offenders

MINIMAL = {
    "primitive": {"navy": {"$value": "#1e3a5f"}, "white": {"$value": "#fff"}},
    "static": {"--pl-space-1": {"$value": "0.25rem"}},
    "semantic": {
        "--pl-accent": {"light": "{navy}", "dark": "{white}", "rgb": True},
        "--pl-bg": {"light": "{white}", "dark": "{navy}"},
    },
    "chart_palette": ["--pl-accent"],
}


def css(spec=None):
    return tokens.build_css(spec or MINIMAL)


# --- resolving -------------------------------------------------------------


def test_an_alias_becomes_the_primitives_variable():
    """Not the colour itself, so dev tools show where it came from."""
    assert tokens.resolve("{navy}", {"navy": "#1e3a5f"}) == "var(--pl-p-navy)"


def test_a_literal_is_left_alone():
    value = "color-mix(in srgb, var(--pl-accent) 85%, black)"
    assert tokens.resolve(value, {}) == value


def test_an_alias_naming_nothing_is_refused():
    """Left alone it emits var(--pl-p-typo), which resolves to nothing and
    paints the element transparent."""
    with pytest.raises(tokens.TokenError, match="names no primitive"):
        tokens.resolve("{typo}", {"navy": "#1e3a5f"})


def test_the_error_lists_the_primitives():
    with pytest.raises(tokens.TokenError, match="navy"):
        tokens.resolve("{typo}", {"navy": "#1e3a5f"})


# --- rgb companions --------------------------------------------------------


def test_channels_are_taken_from_the_hex():
    assert tokens.rgb_channels("#1e3a5f") == "30 58 95"


def test_a_short_hex_expands():
    assert tokens.rgb_channels("#fff") == "255 255 255"


def test_a_non_colour_cannot_have_channels():
    with pytest.raises(tokens.TokenError, match="not a hex colour"):
        tokens.rgb_channels("inherit")


def test_a_computed_value_cannot_ask_for_rgb():
    """color-mix resolves in the browser, so its channels are unknowable here
    — better to refuse than to emit something wrong."""
    spec = dict(MINIMAL)
    spec["semantic"] = {
        "--pl-x": {"light": "color-mix(in srgb, red 50%, blue)", "dark": "{navy}",
                   "rgb": True}
    }
    with pytest.raises(tokens.TokenError, match="not a primitive alias"):
        tokens.build_css(spec)


# --- the stylesheet --------------------------------------------------------


def test_primitives_are_emitted_once():
    assert css().count("--pl-p-navy:") == 1


def test_statics_are_emitted_once():
    assert css().count("--pl-space-1:") == 1


def test_light_lives_in_root():
    out = css()
    root = out.split("@media")[0]
    assert "--pl-accent: var(--pl-p-navy);" in root


def test_dark_is_emitted_twice():
    """Once following the operating system, once for an explicit choice."""
    assert css().count("--pl-accent: var(--pl-p-white);") == 2


def test_the_system_preference_yields_to_a_choice():
    """A viewer who picked light keeps light on a dark-mode machine."""
    assert ':root:not([data-theme="light"])' in css()


def test_an_explicit_choice_comes_last():
    """So it wins over both the default and the media query."""
    out = css()
    assert out.index("@media") < out.index('[data-theme="dark"] {')


def test_an_rgb_companion_is_emitted():
    assert "--pl-accent-rgb: 30 58 95;" in css()


def test_a_token_without_rgb_gets_no_companion():
    assert "--pl-bg-rgb" not in css()


def test_a_semantic_token_missing_a_theme_is_refused():
    spec = dict(MINIMAL)
    spec["semantic"] = {"--pl-x": {"light": "{navy}"}}
    with pytest.raises(tokens.TokenError, match="no 'dark' value"):
        tokens.build_css(spec)


def test_the_file_says_it_is_generated():
    assert css().startswith("/* Generated")


# --- the script ------------------------------------------------------------


def test_the_palette_is_exported():
    assert '"--pl-accent"' in tokens.build_js(MINIMAL)


def test_a_reader_is_exported():
    assert "export function read(" in tokens.build_js(MINIMAL)


# --- the real token file ---------------------------------------------------


def test_the_shipped_tokens_build():
    tokens.build_css(tokens.load())
    tokens.build_js(tokens.load())


def test_the_generated_css_is_current():
    """It is committed, so an edit to tokens.json without a rebuild would ship
    a stylesheet that disagrees with its source."""
    generated = (tokens.STATIC / "css" / "tokens.css").read_text(encoding="utf-8")
    assert generated == tokens.build_css(tokens.load())


def test_every_chart_colour_is_a_real_token():
    spec = tokens.load()
    semantic = tokens.entries(spec["semantic"])
    assert all(name in semantic for name in spec["chart_palette"])


# --- the linter ------------------------------------------------------------


def test_the_source_tree_has_no_raw_colours():
    """One hardcoded hex breaks dark mode in a way nobody notices until
    somebody switches."""
    assert offenders(tokens.DESIGN.parent) == []


def test_the_linter_finds_a_planted_colour(tmp_path):
    (tmp_path / "rogue.css").write_text(".x { color: #ff0000; }", encoding="utf-8")
    assert offenders(tmp_path) != []


def test_the_token_file_itself_is_allowed(tmp_path):
    (tmp_path / "tokens.json").write_text(json.dumps(MINIMAL), encoding="utf-8")
    assert offenders(tmp_path) == []


def test_the_generated_stylesheet_is_allowed(tmp_path):
    (tmp_path / "tokens.css").write_text(":root { --x: #fff; }", encoding="utf-8")
    assert offenders(tmp_path) == []


def test_a_literal_colour_function_is_caught(tmp_path):
    """Catching only hex would let rgb(0 0 0 / 0.4) through, which is just as
    blind to the theme."""
    (tmp_path / "rogue.css").write_text(
        ".x { background: rgb(0 0 0 / 0.4); }", encoding="utf-8"
    )
    assert offenders(tmp_path) != []


def test_a_token_used_inside_a_colour_function_is_fine(tmp_path):
    """Which is what the rgb companions exist for."""
    (tmp_path / "ok.css").write_text(
        ".x { background: rgb(var(--pl-accent-rgb) / 0.1); }", encoding="utf-8"
    )
    assert offenders(tmp_path) == []


def test_the_stylesheet_is_written_only_in_tokens(tmp_path):
    """The shipped stylesheet names no colour of its own."""
    from plinta.shell import tokens as token_module

    css = token_module.STATIC / "css" / "plinta.css"
    assert offenders(css.parent) == []


def test_a_python_file_is_not_scanned(tmp_path):
    """The linter guards what is served, not what generates it."""
    (tmp_path / "thing.py").write_text('COLOUR = "#ff0000"', encoding="utf-8")
    assert offenders(tmp_path) == []

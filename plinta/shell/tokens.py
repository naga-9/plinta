"""Turning `design/tokens.json` into the CSS and JS the shell serves.

Generation rather than hand-writing is what makes "no raw hex outside
tokens.json" enforceable: `lint_hex_colors` can then be a rule with teeth
rather than a convention.
"""
from __future__ import annotations

import json
import pathlib
import re
from typing import Any

#: Where the tokens live, and where the generated files go.
DESIGN = pathlib.Path(__file__).resolve().parent.parent / "design"
TOKENS = DESIGN / "tokens.json"
STATIC = pathlib.Path(__file__).resolve().parent / "static" / "plinta"

#: `{slate-200}` refers to a primitive; anything else is literal CSS.
ALIAS = re.compile(r"\A\{([a-z0-9-]+)\}\Z")

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")

GENERATED = "/* Generated from design/tokens.json by build_tokens. Do not edit. */"


class TokenError(Exception):
    """A token file that cannot be built from."""


def load(path: pathlib.Path | None = None) -> dict[str, Any]:
    """Read the token file."""
    return json.loads((path or TOKENS).read_text(encoding="utf-8"))


def entries(group: dict[str, Any]) -> dict[str, Any]:
    """A group's tokens, without its ``$``-prefixed metadata."""
    return {k: v for k, v in group.items() if not k.startswith("$")}


def resolve(value: str, primitives: dict[str, str]) -> str:
    """One value, with an alias turned into the primitive's variable.

    A primitive is emitted as its own variable rather than inlined, so a
    browser's dev tools show which one a colour came from.

    Raises:
        TokenError: the alias names a primitive that does not exist. Left
            alone it would emit `var(--pl-p-typo)`, which resolves to nothing
            and paints the element transparent.
    """
    match = ALIAS.fullmatch(value)
    if match is None:
        return value
    name = match.group(1)
    if name not in primitives:
        known = ", ".join(sorted(primitives))
        raise TokenError(f"{value} names no primitive (have: {known})")
    return f"var(--pl-p-{name})"


def rgb_channels(hex_value: str) -> str:
    """`#1e3a5f` as `30 58 95`, for a colour used inside `rgb()` with an alpha.

    Raises:
        TokenError: the value is not a hex colour, so there are no channels to
            take. A token asking for `rgb` must resolve to one.
    """
    value = hex_value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    if len(value) != 6 or HEX.fullmatch("#" + value) is None:
        raise TokenError(f"{hex_value!r} is not a hex colour, so it has no channels")
    return " ".join(str(int(value[i : i + 2], 16)) for i in (0, 2, 4))


def build_css(tokens: dict[str, Any]) -> str:
    """The stylesheet: primitives and statics once, semantics per theme.

    Three blocks, and the order matters. `:root` carries light. The media
    query follows the operating system **until the viewer chooses**, which is
    what the `:not([data-theme="light"])` guard preserves. The attribute
    selector comes last so an explicit choice wins over both.
    """
    primitives = {k: v["$value"] for k, v in entries(tokens["primitive"]).items()}
    statics = entries(tokens["static"])
    semantics = entries(tokens["semantic"])

    root = [f"  --pl-p-{name}: {value};" for name, value in primitives.items()]
    root += [f"  {name}: {resolve(v['$value'], primitives)};" for name, v in statics.items()]
    root += _theme_lines(semantics, primitives, "light")

    dark = _theme_lines(semantics, primitives, "dark")
    body = "\n".join(root)
    dark_body = "\n".join(dark)

    return (
        f"{GENERATED}\n\n"
        f":root {{\n{body}\n}}\n\n"
        f"@media (prefers-color-scheme: dark) {{\n"
        f'  :root:not([data-theme="light"]) {{\n{_indent(dark_body)}\n  }}\n'
        f"}}\n\n"
        f'[data-theme="dark"] {{\n{dark_body}\n}}\n'
    )


def _indent(block: str) -> str:
    return "\n".join("  " + line for line in block.splitlines())


def _theme_lines(
    semantics: dict[str, Any], primitives: dict[str, str], theme: str
) -> list[str]:
    lines = []
    for name, spec in semantics.items():
        if theme not in spec:
            raise TokenError(f"{name} has no {theme!r} value")
        value = resolve(spec[theme], primitives)
        lines.append(f"  {name}: {value};")
        if spec.get("rgb"):
            source = spec[theme]
            match = ALIAS.fullmatch(source)
            if match is None:
                raise TokenError(
                    f"{name} asks for rgb but is not a primitive alias, so its "
                    f"channels cannot be known before the browser resolves it"
                )
            lines.append(f"  {name}-rgb: {rgb_channels(primitives[match.group(1)])};")
    return lines


def build_js(tokens: dict[str, Any]) -> str:
    """The chart palette and a reader, for a component that draws with colour.

    A component asks for a token rather than shipping a hex value, so its
    series change with the theme like everything else.
    """
    palette = json.dumps(tokens.get("chart_palette", []), indent=2)
    return f"""// {GENERATED.strip('/* ').strip(' */')}

export const CHART_PALETTE = {palette};

/** The computed value of a CSS custom property, e.g. read('--pl-accent'). */
export function read(name, element) {{
    const target = element || document.documentElement;
    return getComputedStyle(target).getPropertyValue(name).trim();
}}

/** The chart palette as concrete colours, in the theme showing now. */
export function palette() {{
    return CHART_PALETTE.map((name) => read(name));
}}
"""


def write(tokens: dict[str, Any] | None = None, static: pathlib.Path | None = None):
    """Write both generated files. Returns the paths written."""
    tokens = tokens or load()
    static = static or STATIC
    css = static / "css" / "tokens.css"
    js = static / "js" / "tokens.js"
    for path, content in ((css, build_css(tokens)), (js, build_js(tokens))):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return css, js

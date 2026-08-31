"""Every class the markup emits has a rule that defines it.

A class with no rule is invisible: the page returns 200, the element renders,
and it simply has no styling. That is how `pl-stat`, `pl-stat__value` and
`pl-stat__label` shipped — a component emitted three classes and core's
stylesheet defined none of them, so a KPI figure drew at body size.

The same shape as `lint_hex_colors`: a check over the stylesheet that no view
test can make.
"""
import pathlib
import re

import pytest

PACKAGE = pathlib.Path(__file__).resolve().parent.parent
CSS = PACKAGE / "shell" / "static" / "plinta" / "css" / "plinta.css"

#: `.pl-card`, `.pl-card__body`, `.pl-btn--sm` — anywhere in a selector.
SELECTOR = re.compile(r"\.(pl-[a-z0-9_-]+)")

#: `class="pl-card pl-card--flush"`. Anything with a template expression in it
#: is skipped: the value is decided at render and is not a literal to check.
ATTRIBUTE = re.compile(r'class="([^"{}]*)"')


def styled() -> set[str]:
    return set(SELECTOR.findall(CSS.read_text(encoding="utf-8")))


def emitted() -> dict[str, set[str]]:
    """Every `pl-*` class the package writes, and where it writes it."""
    where: dict[str, set[str]] = {}
    for path in list(PACKAGE.rglob("*.html")) + list(PACKAGE.rglob("*.py")):
        if "styles_" in str(path):
            continue  # a style pack names somebody else's classes on purpose
        if path.name.startswith("test_"):
            continue  # what ships is what must be styled, not what tests it
        for group in ATTRIBUTE.findall(path.read_text(encoding="utf-8")):
            for name in group.split():
                if name.startswith("pl-"):
                    where.setdefault(name, set()).add(path.name)
    return where


def vocabulary() -> dict[str, set[str]]:
    """The class names a style pack may rename — all of them ours."""
    from plinta.utils.styles import DEFAULT

    where: dict[str, set[str]] = {}
    for key, value in DEFAULT.items():
        for name in value.split():
            if name.startswith("pl-"):
                where.setdefault(name, set()).add(f"styles.DEFAULT[{key!r}]")
    return where


def sources() -> dict[str, set[str]]:
    combined = emitted()
    for name, places in vocabulary().items():
        combined.setdefault(name, set()).update(places)
    return combined


def test_the_stylesheet_is_found():
    """Guards everything below: a missing file would style nothing and pass."""
    assert CSS.exists()
    assert len(styled()) > 40


@pytest.mark.parametrize("name", sorted(sources()))
def test_every_emitted_class_has_a_rule(name):
    assert name in styled(), (
        f"{name} is emitted by {', '.join(sorted(sources()[name]))} and no rule "
        f"defines it — the element renders unstyled and nothing fails."
    )


def test_the_vocabulary_is_fully_styled():
    """A pack overriding only some keys leaves ours in place for the rest, so
    every default must resolve to something real."""
    assert not set(vocabulary()) - styled()

"""What the templates must satisfy to render at all.

Both checks here exist because the demo shipped screens that were broken in
ways no view test noticed: a page returns 200 with its stylesheet missing and
its comments printed on the page.
"""
import pathlib
import re

import pytest
from django.contrib.staticfiles import finders
from django.template.loader import get_template

PACKAGE = pathlib.Path(__file__).resolve().parent.parent

#: Django's lexer matches `{# ... #}` without DOTALL, so a comment carrying a
#: newline is not a comment — it is text, and it renders on the page.
COMMENT = re.compile(r"\{#((?:[^#]|#(?!\}))*?)#\}", re.DOTALL)

#: Every stylesheet and script `base.html` asks for.
ASSETS = [
    "plinta/css/tokens.css",
    "plinta/css/plinta.css",
    "plinta/js/theme-toggle.js",
    "plinta/js/sidebar.js",
    "plinta/js/tag-select.js",
    "plinta/js/filter-cascade.js",
    "plinta/js/menu-groups.js",
    "plinta/js/keep-scroll.js",
    "plinta/js/client.js",
]


def templates():
    return sorted(PACKAGE.rglob("*.html"))


def test_there_are_templates_to_check():
    assert templates()


@pytest.mark.parametrize("path", templates(), ids=lambda p: p.name)
def test_no_comment_spans_a_line(path):
    """A `{# #}` carrying a newline renders as text.

    Django's comment syntax is single-line. Nothing warns about the multi-line
    form: the page still returns 200, with the comment printed at the top.
    Use `{% comment %}` when it will not fit on one line.
    """
    offenders = [m.group(0) for m in COMMENT.finditer(path.read_text(encoding="utf-8"))
                 if "\n" in m.group(1)]
    assert not offenders, (
        f"{path.name}: {len(offenders)} multi-line {{# #}} would render as text; "
        "use {% comment %}"
    )


@pytest.mark.parametrize("asset", ASSETS)
def test_the_shell_assets_resolve(asset):
    """A path `base.html` names must be found by a staticfiles finder.

    They are found through the app they live in, so an asset outside every
    installed app's `static/` is a 404 the page does not report — the screen
    renders unstyled and nothing fails.
    """
    assert finders.find(asset), f"{asset} is not on any finder's search path"


def test_the_base_template_renders():
    """The lexer accepts it. A template error here breaks every screen."""
    assert get_template("plinta/shell/base.html")

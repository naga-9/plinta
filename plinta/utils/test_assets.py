"""Stylesheets contributed by packages."""
import pytest

from plinta.utils.assets import AssetError, register_stylesheet, stylesheets


def test_a_sheet_is_registered_and_returned(stylesheet_registry):
    register_stylesheet("plinta/kanban/kanban.css")
    assert [s.path for s in stylesheets()] == ["plinta/kanban/kanban.css"]


def test_order_decides_the_cascade(stylesheet_registry):
    register_stylesheet("late.css", order=200)
    register_stylesheet("early.css", order=10)
    assert [s.path for s in stylesheets()] == ["early.css", "late.css"]


def test_ties_break_on_path_not_import_order(stylesheet_registry):
    """Two packages at the same order must not swap places between runs
    depending on which app was imported first."""
    register_stylesheet("b.css")
    register_stylesheet("a.css")
    assert [s.path for s in stylesheets()] == ["a.css", "b.css"]


def test_a_path_is_registered_once(stylesheet_registry):
    register_stylesheet("one.css")
    with pytest.raises(AssetError, match="already registered"):
        register_stylesheet("one.css")


@pytest.mark.parametrize(
    "path",
    [
        "https://cdn.example.com/x.css",
        "http://cdn.example.com/x.css",
        "//cdn.example.com/x.css",
        "data:text/css,body{}",
    ],
)
def test_a_remote_sheet_is_refused(stylesheet_registry, path):
    """Core loads nothing from a CDN, and neither does a package registering
    here. A remote sheet is the consumer's decision and belongs in the
    template block where they can see it."""
    with pytest.raises(AssetError, match="remote"):
        register_stylesheet(path)


@pytest.mark.parametrize("path", ["", "   ", None])
def test_an_empty_path_is_refused(stylesheet_registry, path):
    with pytest.raises(AssetError, match="needs a path"):
        register_stylesheet(path)


def test_nothing_is_registered_by_default(stylesheet_registry):
    """Core's own two sheets are linked directly, not registered — they live
    in a block a consumer replaces wholesale."""
    assert stylesheets() == []


# --- scripts ----------------------------------------------------------------


def test_a_script_is_registered(stylesheet_registry):
    from plinta.utils.assets import register_script, scripts

    register_script("plinta/tomselect/adapter.js")
    assert [s.path for s in scripts()] == ["plinta/tomselect/adapter.js"]


def test_order_decides_load_order(stylesheet_registry):
    """A package's glue must load after its vendor, so this is not cosmetic."""
    from plinta.utils.assets import register_script, scripts

    register_script("glue.js", order=210)
    register_script("vendor.js", order=200)
    assert [s.path for s in scripts()] == ["vendor.js", "glue.js"]


def test_a_script_defers_by_default(stylesheet_registry):
    """The exception is one that must run before the first paint."""
    from plinta.utils.assets import register_script

    assert register_script("a.js").defer is True
    assert register_script("b.js", defer=False).defer is False


def test_a_remote_script_is_refused(stylesheet_registry):
    """An install must work offline and under a strict CSP (§17.1)."""
    from plinta.utils.assets import AssetError, register_script

    with pytest.raises(AssetError, match="Vendor it"):
        register_script("https://cdn.example.com/tom-select.js")


def test_a_script_is_registered_once(stylesheet_registry):
    from plinta.utils.assets import AssetError, register_script

    register_script("one.js")
    with pytest.raises(AssetError, match="already registered"):
        register_script("one.js")

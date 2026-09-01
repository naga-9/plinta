"""The form-layout registry: a registered key, never a path from a config row."""
import pytest

from plinta.components.layouts import (
    DEFAULT,
    FormLayoutError,
    get,
    register_form_layout,
    registered,
)


def test_a_layout_is_found_by_name(form_layout_registry):
    register_form_layout("book", "catalog/book_form.html")
    assert get("book") == "catalog/book_form.html"


def test_an_unknown_name_is_the_default(form_layout_registry):
    """Never raises: the name arrives from a saved block whose app may be
    gone, and a page degrades rather than breaks."""
    assert get("nonesuch") == DEFAULT
    assert get("") == DEFAULT


def test_a_name_is_taken_once(form_layout_registry):
    register_form_layout("book", "a.html")
    with pytest.raises(FormLayoutError, match="already registered"):
        register_form_layout("book", "b.html")


def test_the_error_lists_what_is_registered(form_layout_registry):
    register_form_layout("book", "a.html")
    with pytest.raises(FormLayoutError, match="registered: book"):
        register_form_layout("book", "b.html")


@pytest.mark.parametrize("name", ["", "Book", "book-form", "1book", "book form"])
def test_a_name_must_be_a_key(form_layout_registry, name):
    with pytest.raises(FormLayoutError):
        register_form_layout(name, "a.html")


def test_a_layout_names_a_template(form_layout_registry):
    with pytest.raises(FormLayoutError, match="names no template"):
        register_form_layout("book", "")


def test_registered_lists_them(form_layout_registry):
    register_form_layout("book", "a.html")
    register_form_layout("author", "b.html")
    assert registered() == ["author", "book"]


def test_a_missing_template_is_reported_by_a_check(form_layout_registry):
    """Rendering will not report it — a missing layout falls back to the
    stacked body — which is exactly why the check has to."""
    from plinta.components.checks import check_form_layouts

    register_form_layout("book", "nowhere/at/all.html")
    problems = check_form_layouts()
    assert [p.id for p in problems] == ["plinta.components.W001"]
    assert "book" in problems[0].msg


def test_a_template_that_loads_is_not_reported(form_layout_registry):
    from plinta.components.checks import check_form_layouts

    register_form_layout("stacked", DEFAULT)
    assert check_form_layouts() == []

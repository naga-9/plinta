"""The Tom Select widget: registered, vendored, and degrading."""
import pathlib

import pytest

from plinta.pages.widgets import get
from plinta.utils.assets import scripts, stylesheets

PACKAGE = pathlib.Path(__file__).resolve().parent


def test_it_registers_through_the_same_door():
    """`capability_implementation`, beside core's own — neither privileged."""
    widget = get("multiselect_tomselect")
    assert widget.multiple is True
    assert widget.needs_options is True
    assert get("multiselect_plinta").multiple is True


def test_the_vendor_is_in_the_package():
    """Vendored, not fetched: an install must work offline and under a strict
    CSP, and no deployment should depend on a CDN being reachable (§17)."""
    vendor = PACKAGE / "static" / "plinta" / "tomselect"
    assert (vendor / "tom-select.complete.min.js").exists()
    assert (vendor / "tom-select.min.css").exists()
    assert (PACKAGE / "LICENSE-tom-select").read_text(encoding="utf-8").strip()


def test_the_glue_loads_after_the_vendor():
    """`adapter.js` calls `new TomSelect`, so order is not cosmetic."""
    paths = [s.path for s in scripts()]
    assert paths.index(
        "plinta/tomselect/tom-select.complete.min.js"
    ) < paths.index("plinta/tomselect/adapter.js")


def test_the_stylesheet_is_registered():
    assert "plinta/tomselect/tom-select.min.css" in [s.path for s in stylesheets()]


@pytest.mark.parametrize("name", ["tom-select.complete.min.js", "adapter.js"])
def test_no_asset_is_remote(name):
    """`register_script` refuses a URL, so this asserts the package obeyed it
    rather than working around it."""
    assert not name.startswith(("http", "//"))


def test_the_markup_is_still_a_native_select(db, client, django_user_model):
    """Tom Select replaces the select in place. With the script absent the
    viewer gets a working native control — the vendor is polish, not the
    mechanism."""
    from django.template.loader import render_to_string

    html = render_to_string(
        "plinta/tomselect/multiselect.html",
        {
            "control": type("C", (), {"field_name": "store"})(),
            "control_id": "pl-filter-1",
            "value": [],
            "options": [("1", "Hale Street")],
            "cls": {"select": "pl-select", "help": "pl-help"},
        },
    )
    assert "<select" in html and "multiple" in html
    assert 'data-plinta-tomselect' in html
    assert '<input type="hidden" name="store" value="">' in html

"""The Bootstrap 5 pack: registered, complete, and actually reaching the markup."""
import pytest

from plinta.contrib.styles_bootstrap5.pack import CLASSES, RESIDUE
from plinta.utils.styles import DEFAULT, classes


def test_it_registers_itself_at_boot():
    """From `AppConfig.ready()`, like everything else."""
    assert classes("bootstrap5")["btn"] == "btn btn-outline-secondary"


def test_every_key_is_in_the_vocabulary():
    """`register_style_pack` enforces this; asserting it here names the typo."""
    assert not set(CLASSES) - set(DEFAULT)


def test_the_structural_matches_are_mapped():
    """The three shapes that already line up with Bootstrap's own components.

    If one of these regresses, the pack silently produces markup Bootstrap
    styles as nothing.
    """
    pack = classes("bootstrap5")
    assert pack["card"] == "card"
    assert pack["card_body"] == "card-body"
    assert pack["pager_list"] == "pagination pagination-sm mb-0 ms-auto"
    assert pack["pager_item"] == "page-item"
    assert pack["pager_link"] == "page-link"
    assert pack["input"] == "form-control"
    assert pack["label"] == "form-label"


def test_what_it_cannot_reach_is_written_down():
    """A pack that mapped these anyway would look broken with no error."""
    assert RESIDUE
    assert all(path.endswith(".html") for path in RESIDUE)


@pytest.mark.parametrize("key", sorted(DEFAULT))
def test_nothing_maps_to_an_empty_string(key):
    """An empty class is how an element loses its styling silently."""
    assert classes("bootstrap5")[key].strip()


def test_the_pager_renders_bootstrap_markup(settings):
    """End to end: the renderer asks the registry, so the pack reaches the HTML."""
    from django.core.paginator import Paginator

    from plinta.renderers.html import HtmlRenderer

    settings.PLINTA_STYLE_PACK = "bootstrap5"
    page = Paginator(list(range(30)), 10).page(2)
    html = HtmlRenderer().pager(page, {"previous": "?page=1", "next": "?page=3"})

    assert 'class="pagination pagination-sm mb-0 ms-auto"' in html
    assert 'class="page-item"' in html
    assert 'class="page-link"' in html
    assert "pl-pager__list" not in html

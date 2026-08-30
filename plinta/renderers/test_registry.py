"""Registering a format, and what stands in when one is not installed."""
import pytest

from plinta.renderers.base import Renderer
from plinta.renderers.registry import (
    RendererError,
    get,
    is_registered,
    registered,
    require,
)


class Html(Renderer):
    def render(self, rows, fields, config, user):
        return "<table></table>"


class Csv(Renderer):
    content_type = "text/csv"
    extension = "csv"

    def render(self, rows, fields, config, user):
        return "a,b"


# --- registering -----------------------------------------------------------


def test_registers_a_class(renderer_registry):
    renderer_registry.register_renderer("csv")(Csv)
    assert is_registered("csv")


def test_the_class_is_instantiated_once(renderer_registry):
    """A renderer holds no per-call state, so two lookups are the same object."""
    renderer_registry.register_renderer("csv")(Csv)
    assert require("csv") is require("csv")


def test_the_decorator_returns_the_class(renderer_registry):
    assert renderer_registry.register_renderer("csv")(Csv) is Csv


def test_a_duplicate_is_refused(renderer_registry):
    renderer_registry.register_renderer("csv")(Csv)
    with pytest.raises(RendererError, match="already registered"):
        renderer_registry.register_renderer("csv")(Csv)


@pytest.mark.parametrize("name", ["CSV", "1st", "with-dash", "", "with space"])
def test_an_unusable_name_is_refused(renderer_registry, name):
    with pytest.raises(RendererError):
        renderer_registry.register_renderer(name)(Csv)


def test_registered_lists_them(renderer_registry):
    renderer_registry.register_renderer("html")(Html)
    renderer_registry.register_renderer("csv")(Csv)
    assert sorted(registered()) == ["csv", "html"]


# --- substitution ----------------------------------------------------------


def test_a_registered_format_is_its_own(renderer_registry):
    renderer_registry.register_renderer("html")(Html)
    renderer_registry.register_renderer("csv")(Csv)
    assert isinstance(get("csv"), Csv)


def test_an_uninstalled_format_falls_back_to_html(renderer_registry):
    """A report defined against xlsx runs without contrib.export, to screen."""
    renderer_registry.register_renderer("html")(Html)
    assert isinstance(get("xlsx"), Html)


def test_a_caller_never_asks_whether_export_is_installed(renderer_registry):
    renderer_registry.register_renderer("html")(Html)
    assert get("xlsx").render([], [], {}, None) == "<table></table>"


def test_with_nothing_registered_even_the_fallback_fails(renderer_registry):
    with pytest.raises(RendererError, match="none for 'html'"):
        get("xlsx")


# --- content negotiation does not substitute -------------------------------


def test_require_refuses_an_uninstalled_format(renderer_registry):
    """Answering an xlsx request with an HTML page is worse than refusing it."""
    renderer_registry.register_renderer("html")(Html)
    with pytest.raises(RendererError, match="no renderer for 'xlsx'"):
        require("xlsx")


def test_the_error_lists_what_is_registered(renderer_registry):
    renderer_registry.register_renderer("html")(Html)
    with pytest.raises(RendererError, match="registered: html"):
        require("xlsx")


def test_require_returns_a_registered_one(renderer_registry):
    renderer_registry.register_renderer("csv")(Csv)
    assert isinstance(require("csv"), Csv)


# --- the contract ----------------------------------------------------------


def test_the_base_renderer_must_be_implemented():
    with pytest.raises(NotImplementedError):
        Renderer().render([], [], {}, None)


def test_a_renderer_declares_how_it_is_served(renderer_registry):
    renderer_registry.register_renderer("csv")(Csv)
    assert require("csv").content_type == "text/csv"
    assert require("csv").extension == "csv"


def test_html_is_the_default_content_type():
    assert Renderer.content_type.startswith("text/html")
    assert Renderer.extension == ""

"""Registering a component, and what a block gets when one is missing."""
import pytest

from plinta.components.base import Component, ComponentConfig, Mode
from plinta.components.registry import (
    ComponentError,
    find,
    get,
    is_registered,
    registered,
)


class Heatmap(Component):
    def render(self, config, user, **context):
        return "<div></div>"


# --- registering -----------------------------------------------------------


def test_registers_a_class(component_registry):
    component_registry.register_component("heatmap")(Heatmap)
    assert is_registered("heatmap")


def test_the_class_is_instantiated_once(component_registry):
    component_registry.register_component("heatmap")(Heatmap)
    assert get("heatmap") is get("heatmap")


def test_the_decorator_returns_the_class(component_registry):
    assert component_registry.register_component("heatmap")(Heatmap) is Heatmap


def test_a_label_is_for_the_picker(component_registry):
    component_registry.register_component("heatmap", label="Heat map")(Heatmap)
    assert get("heatmap").label == "Heat map"


def test_a_duplicate_is_refused(component_registry):
    """Two packages cannot silently fight over a registry key."""
    component_registry.register_component("heatmap")(Heatmap)
    with pytest.raises(ComponentError, match="already registered"):
        component_registry.register_component("heatmap")(Heatmap)


@pytest.mark.parametrize("name", ["Heatmap", "1st", "with-dash", "", "with space"])
def test_an_unusable_name_is_refused(component_registry, name):
    with pytest.raises(ComponentError):
        component_registry.register_component(name)(Heatmap)


def test_registered_lists_them(component_registry):
    component_registry.register_component("heatmap")(Heatmap)
    assert list(registered()) == ["heatmap"]


# --- the empty slot --------------------------------------------------------


def test_find_returns_none_for_an_uninstalled_component(component_registry):
    """A page must not break because a component's package was removed."""
    assert find("gone") is None


def test_find_returns_a_registered_one(component_registry):
    component_registry.register_component("heatmap")(Heatmap)
    assert isinstance(find("heatmap"), Heatmap)


def test_get_raises_instead(component_registry):
    with pytest.raises(ComponentError, match="no component named"):
        get("gone")


def test_the_error_lists_what_is_registered(component_registry):
    component_registry.register_component("heatmap")(Heatmap)
    with pytest.raises(ComponentError, match="registered: heatmap"):
        get("other")


# --- the contract ----------------------------------------------------------


def test_the_base_component_must_be_implemented():
    with pytest.raises(NotImplementedError):
        Component().render(ComponentConfig(), None)


def test_a_component_defaults_to_fetch():
    assert Component.mode is Mode.FETCH


def test_a_component_may_declare_inline():
    class Kpi(Component):
        mode = Mode.INLINE

    assert Kpi.mode is Mode.INLINE

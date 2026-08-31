"""Fixtures that isolate plinta's module-level registries between tests."""
import pytest

from plinta.dates import ranges
from plinta.datasources import annotations, modifiers
from plinta.events import signals
from plinta.pages import widgets
from plinta.permissions import actions, policies
from plinta.forms import overrides
from plinta.utils import assets, placeholders, styles


@pytest.fixture
def placeholder_registry():
    """Empty placeholder registry, restored afterwards."""
    saved = dict(placeholders._registry)
    placeholders._registry.clear()
    yield placeholders
    placeholders._registry.clear()
    placeholders._registry.update(saved)


@pytest.fixture
def widget_registry():
    """Empty filter-widget registry, restored afterwards."""
    saved = dict(widgets._registry)
    widgets._registry.clear()
    yield widgets
    widgets._registry.clear()
    widgets._registry.update(saved)


@pytest.fixture
def stylesheet_registry():
    """Empty asset registries — stylesheets and scripts — restored after."""
    saved, saved_scripts = dict(assets._registry), dict(assets._scripts)
    assets._registry.clear()
    assets._scripts.clear()
    yield assets
    assets._registry.clear()
    assets._registry.update(saved)
    assets._scripts.clear()
    assets._scripts.update(saved_scripts)


@pytest.fixture
def style_registry():
    """Style packs reset to plinta's own, restored afterwards.

    Not emptied: `classes()` must always resolve, and the built-in pack is
    what every default resolves to.
    """
    saved = dict(styles._registry)
    styles._registry.clear()
    styles._registry[styles.PLINTA] = dict(styles.DEFAULT)
    yield styles
    styles._registry.clear()
    styles._registry.update(saved)


@pytest.fixture
def range_registry():
    """Empty range registry, restored afterwards."""
    saved = dict(ranges._registry)
    ranges._registry.clear()
    yield ranges
    ranges._registry.clear()
    ranges._registry.update(saved)


@pytest.fixture
def override_registry():
    """Empty widget-override registry, restored afterwards."""
    saved = dict(overrides._registry)
    overrides._registry.clear()
    yield overrides
    overrides._registry.clear()
    overrides._registry.update(saved)


@pytest.fixture
def listen():
    """Connect receivers for a test and disconnect them afterwards.

    Returns ``listen(signal, fn)``. Connects with ``weak=False`` so a function
    defined inside a test is not garbage-collected before the signal fires.
    """
    connected = []

    def _listen(signal, fn, sender=None):
        signal.connect(fn, sender=sender, weak=False)
        connected.append((signal, fn, sender))
        return fn

    yield _listen
    for signal, fn, sender in connected:
        signal.disconnect(fn, sender=sender)


@pytest.fixture(autouse=True)
def _no_leaked_receivers():
    """Fail loudly if a test leaves a receiver connected."""
    before = {s: len(s.receivers) for s in signals.ALL}
    yield
    leaked = {s._plinta_name: len(s.receivers) - before[s]
              for s in signals.ALL if len(s.receivers) != before[s]}
    assert not leaked, f"receivers left connected: {leaked}"


@pytest.fixture
def policy_registry():
    """Empty policy registry, restored afterwards."""
    saved = dict(policies._registry)
    policies._registry.clear()
    yield policies
    policies._registry.clear()
    policies._registry.update(saved)


@pytest.fixture
def action_registry():
    """Empty action registry, restored afterwards."""
    saved = dict(actions._registry)
    actions._registry.clear()
    yield actions
    actions._registry.clear()
    actions._registry.update(saved)


@pytest.fixture
def modifier_registry():
    """Empty queryset-modifier registry, restored afterwards."""
    saved = dict(modifiers._registry)
    modifiers._registry.clear()
    yield modifiers
    modifiers._registry.clear()
    modifiers._registry.update(saved)


@pytest.fixture
def shell_link_registry():
    """Empty shell-link registry, restored afterwards."""
    from plinta.shell import links

    saved = dict(links._registry)
    links._registry.clear()
    yield links
    links._registry.clear()
    links._registry.update(saved)


@pytest.fixture
def capability_registry():
    """Empty capability registry, restored afterwards."""
    from plinta.blocks import capabilities

    saved = dict(capabilities._registry)
    capabilities._registry.clear()
    yield capabilities
    capabilities._registry.clear()
    capabilities._registry.update(saved)


@pytest.fixture
def component_registry():
    """Empty component registry, restored afterwards."""
    from plinta.components import registry

    saved = dict(registry._registry)
    registry._registry.clear()
    yield registry
    registry._registry.clear()
    registry._registry.update(saved)


@pytest.fixture
def renderer_registry():
    """Empty renderer registry, restored afterwards."""
    from plinta.renderers import registry

    saved = dict(registry._registry)
    registry._registry.clear()
    yield registry
    registry._registry.clear()
    registry._registry.update(saved)


@pytest.fixture
def field_renderer_registry():
    """Empty field-renderer registry, restored afterwards."""
    from plinta.renderers import fields as field_renderers

    saved = dict(field_renderers._registry)
    field_renderers._registry.clear()
    yield field_renderers
    field_renderers._registry.clear()
    field_renderers._registry.update(saved)


@pytest.fixture
def annotation_registry():
    """Empty annotation registry, restored afterwards."""
    saved = dict(annotations._registry)
    annotations._registry.clear()
    yield annotations
    annotations._registry.clear()
    annotations._registry.update(saved)

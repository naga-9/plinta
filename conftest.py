"""Fixtures that isolate plinta's module-level registries between tests."""
import pytest

from plinta.dates import ranges
from plinta.forms import overrides
from plinta.utils import placeholders


@pytest.fixture
def placeholder_registry():
    """Empty placeholder registry, restored afterwards."""
    saved = dict(placeholders._registry)
    placeholders._registry.clear()
    yield placeholders
    placeholders._registry.clear()
    placeholders._registry.update(saved)


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

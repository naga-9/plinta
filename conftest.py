"""Fixtures that isolate plinta's module-level registries between tests."""
import pytest

from plinta.dates import ranges
from plinta.events import signals
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

"""Registering a named narrowing, and refusing one nobody registered."""
import pytest

from plinta.datasources.modifiers import ModifierError, apply_modifier, get_modifier
from tests.testapp.models import Book

pytestmark = pytest.mark.django_db


def test_registers_and_resolves(modifier_registry):
    @modifier_registry.register_queryset_modifier("mine")
    def mine(queryset, user=None, **kwargs):
        return queryset.filter(owner=user)

    assert get_modifier("mine") is mine


def test_registers_as_a_call(modifier_registry):
    modifier_registry.register_queryset_modifier("mine", lambda qs, user=None, **kw: qs)
    assert set(modifier_registry.registered()) == {"mine"}


def test_a_duplicate_is_refused(modifier_registry):
    modifier_registry.register_queryset_modifier("mine", lambda qs, user=None, **kw: qs)
    with pytest.raises(ModifierError, match="already registered"):
        modifier_registry.register_queryset_modifier("mine", lambda qs, user=None, **kw: qs)


@pytest.mark.parametrize("name", ["Mine", "1st", "with-dash", "", "with space"])
def test_an_unusable_name_is_refused(modifier_registry, name):
    with pytest.raises(ModifierError):
        modifier_registry.register_queryset_modifier(name, lambda qs, user=None, **kw: qs)


def test_an_unregistered_name_fails_loudly(modifier_registry):
    """Configuration naming a modifier that does not exist must not silently
    render every row it was meant to hide."""
    with pytest.raises(ModifierError, match="no queryset modifier named"):
        get_modifier("nonsense")


def test_the_error_lists_what_is_registered(modifier_registry):
    modifier_registry.register_queryset_modifier("mine", lambda qs, user=None, **kw: qs)
    with pytest.raises(ModifierError, match="registered: mine"):
        get_modifier("theirs")


def test_apply_narrows_the_queryset(modifier_registry, django_user_model):
    ada = django_user_model.objects.create(username="ada")
    bob = django_user_model.objects.create(username="bob")
    Book.objects.create(title="Dune", owner=ada)
    Book.objects.create(title="Emma", owner=bob)

    modifier_registry.register_queryset_modifier(
        "mine", lambda qs, user=None, **kw: qs.filter(owner=user)
    )
    assert apply_modifier("mine", Book.objects.all(), ada).count() == 1


def test_a_modifier_receives_extra_arguments(modifier_registry):
    seen = {}

    def capture(queryset, user=None, **kwargs):
        seen.update(kwargs)
        return queryset

    modifier_registry.register_queryset_modifier("capture", capture)
    apply_modifier("capture", Book.objects.all(), None, tab="open")
    assert seen == {"tab": "open"}

"""Token resolution, and the three boundaries that keep it from being a language."""
import pytest

from plinta.utils.placeholders import (
    Context,
    PlaceholderError,
    register_placeholder,
    registered,
    resolve,
    resolve_values,
    unresolved,
)

CTX = Context()


def test_registers_and_resolves(placeholder_registry):
    register_placeholder("answer", lambda ctx: 42)
    assert resolve("__ANSWER__", CTX) == 42


def test_registers_as_a_decorator(placeholder_registry):
    @register_placeholder("answer")
    def answer(ctx):
        return 42

    assert registered() == {"answer"}
    assert answer(CTX) == 42, "the decorator returns the function, not the registration"


def test_a_resolver_sees_the_context(placeholder_registry):
    register_placeholder("me", lambda ctx: ctx.user)
    assert resolve("__ME__", Context(user="ada")) == "ada"


def test_a_duplicate_name_is_refused(placeholder_registry):
    register_placeholder("answer", lambda ctx: 1)
    with pytest.raises(PlaceholderError, match="already registered"):
        register_placeholder("answer", lambda ctx: 2)


@pytest.mark.parametrize("name", ["Answer", "__answer__", "1st", "with-dash", ""])
def test_an_unusable_name_is_refused(placeholder_registry, name):
    with pytest.raises(PlaceholderError):
        register_placeholder(name, lambda ctx: 1)


def test_an_unregistered_token_is_left_untouched(placeholder_registry):
    """Blanking it would widen the filter that contains it."""
    assert resolve("__NOBODY__", CTX) == "__NOBODY__"


@pytest.mark.parametrize(
    "value",
    [
        "plain", "", 7, None, True,
        "__lower__",     # tokens are uppercase, so data is never mistaken for one
        "__A B__",
        "__1ST__",       # must start with a letter
        "_ME_",          # one underscore is not the delimiter
    ],
)
def test_non_tokens_pass_through(placeholder_registry, value):
    assert resolve(value, CTX) == value


@pytest.mark.parametrize("value", ['__ME__\n', "__ME__ ", " __ME__", "__ME__x"])
def test_whitespace_or_padding_means_it_is_not_a_token(placeholder_registry, value):
    """`fullmatch`, not `$` — which in Python also matches before a trailing newline."""
    register_placeholder("me", lambda ctx: 9)
    assert resolve(value, CTX) == value


def test_resolves_inside_a_filter_dict(placeholder_registry):
    register_placeholder("me", lambda ctx: 9)
    assert resolve_values({"owner": "__ME__", "status": "open"}, CTX) == {
        "owner": 9,
        "status": "open",
    }


def test_resolves_inside_a_list_value(placeholder_registry):
    register_placeholder("me", lambda ctx: 9)
    assert resolve_values({"owner__in": ["__ME__", 3]}, CTX) == {"owner__in": [9, 3]}


def test_a_resolver_may_return_a_list(placeholder_registry):
    register_placeholder("watchlist", lambda ctx: [1, 2])
    assert resolve_values({"id__in": "__WATCHLIST__"}, CTX) == {"id__in": [1, 2]}


def test_unresolved_reports_missing_providers(placeholder_registry):
    register_placeholder("here", lambda ctx: 1)
    values = {"a": "__HERE__", "b": "__GONE__", "c__in": ["__ALSO_GONE__"]}
    assert unresolved(values) == {"gone", "also_gone"}


def test_a_token_is_a_whole_value_not_a_substring(placeholder_registry):
    """A token supplies a value; it never expands into a field path or operator."""
    register_placeholder("me", lambda ctx: 9)
    assert resolve("prefix__ME__", CTX) == "prefix__ME__"
    assert resolve_values({"owner__ME__": 1}, CTX) == {"owner__ME__": 1}


def test_a_resolver_runs_per_call(placeholder_registry):
    """Never cached globally — a user-scoped token depends on who is asking."""
    calls = []
    register_placeholder("count", lambda ctx: calls.append(1) or len(calls))
    assert resolve("__COUNT__", CTX) == 1
    assert resolve("__COUNT__", CTX) == 2

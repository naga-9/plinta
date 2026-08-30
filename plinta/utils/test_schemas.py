"""What a filter-style value may be, and what it may not."""
import pytest
from pydantic import ValidationError

from plinta.utils.schemas import FilterValuesAdapter


@pytest.mark.parametrize("value", [
    {},
    {"status": "open"},
    {"quantity__gte": 10},
    {"price": 9.99},
    {"in_print": True},
    {"region": None},
    {"region__in": ["North", "South"]},
    {"id__in": [1, 2, 3]},
    {"mixed__in": ["a", 1, None, True]},
    {"a": "x", "b": 2, "c__in": [3]},
])
def test_accepts_scalars_and_lists_of_scalars(value):
    assert FilterValuesAdapter.validate_python(value) == value


@pytest.mark.parametrize("value", [
    {"a": {"nested": 1}},          # a dict is not a filter value
    {"a": [[1]]},                  # nor a list of lists
    {"a": [{"b": 1}]},             # nor a list of dicts
    {"a": object()},               # nor an arbitrary object
])
def test_rejects_anything_nested_or_unserialisable(value):
    with pytest.raises(ValidationError):
        FilterValuesAdapter.validate_python(value)


def test_rejects_a_non_dict():
    with pytest.raises(ValidationError):
        FilterValuesAdapter.validate_python(["status", "open"])


def test_keys_are_not_validated():
    """They are field paths on a model this layer does not know about."""
    assert FilterValuesAdapter.validate_python({"nonsense__wat": 1}) == {"nonsense__wat": 1}


def test_a_placeholder_token_survives_validation():
    """Tokens are resolved later, so they must pass through as ordinary strings."""
    value = {"owner": "__CURRENT_USER__", "id__in": ["__MY_STORES__"]}
    assert FilterValuesAdapter.validate_python(value) == value


def test_a_union_failure_reports_one_error_per_branch():
    """Known and deliberate: layer 7 collapses these before a user sees them."""
    with pytest.raises(ValidationError) as exc:
        FilterValuesAdapter.validate_python({"a": {"nested": 1}})
    branches = {err["loc"][1] for err in exc.value.errors() if len(err["loc"]) > 1}
    assert {"str", "int", "float", "bool"} <= branches

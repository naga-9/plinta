"""Shared pydantic adapters for filter-style JSON."""
from typing import Union

from pydantic import TypeAdapter

_JSONScalar = Union[str, int, float, bool, None]
_FilterValue = Union[_JSONScalar, list[_JSONScalar]]

#: Validates ``{field_path: scalar | list[scalar]}``.
#:
#: Keys are field paths with an optional ``__lookup`` suffix and are not
#: validated here — they are model-specific, so the caller that knows the model
#: checks them. This enforces value shape only, which still rejects nested
#: dicts and non-JSON scalars.
FilterValuesAdapter = TypeAdapter(dict[str, _FilterValue])

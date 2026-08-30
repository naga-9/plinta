---
name: add-placeholder
description: Register a token that resolves to a value inside filter-style config — __CURRENT_USER__, __CURRENT_FISCAL_YEAR__, __MY_WATCHLIST__. Use when a stored filter needs a value that is only known at query time, or per user.
---

# Add a placeholder

A placeholder is a token written into stored configuration that resolves to a
**value** when the query runs.

```json
{"owner": "__CURRENT_USER__", "fiscal_year": "__CURRENT_FISCAL_YEAR__"}
```

## When to use this

- the value depends on **who is asking** — the current user, their team, their watchlist
- the value depends on **when the query runs** — today, this quarter
- the value belongs to a package core must not import, such as a fiscal calendar

Do **not** use it when the value is fixed at configuration time. Write the value.

## Steps

1. Put the resolver in `placeholders.py` in your app.

```python
from plinta.utils import register_placeholder

@register_placeholder("my_watchlist")
def my_watchlist(ctx):
    return list(ctx.user.watchlists.values_list("instrument_id", flat=True))
```

2. Import that module from `AppConfig.ready()` so it registers at startup.

```python
class MyAppConfig(AppConfig):
    def ready(self):
        from . import placeholders  # noqa: F401
```

3. Use the token in any filter-style value: a page filter, a `FilterSet`, a
   `Block.base_filter`, `create_defaults`, or a scheduled report's filters.

## The contract

| | |
|---|---|
| Name | lowercase `[a-z][a-z0-9_]*`; the token is its uppercase form wrapped in `__` |
| Signature | `fn(ctx) -> value`, where `ctx.user` is the requesting user |
| Returns | a scalar or a list of scalars — never a field path, never an operator |
| Runs | once per resolution, never cached |

## Rules

**A token supplies a value, never a lookup.** `{"date": "__CURRENT_QUARTER__"}`
is legitimate; a token that expands into `date__gte` is not. That boundary is
what stops a token widening a filter into fields its author never named.

**The whole value or nothing.** `"prefix__ME__"` is not a token. A token is
matched against the entire value.

**The returned type must suit the lookup.** A list against an `exact` lookup is
a configuration error. Return what the lookup expects.

**Registering twice raises.** `PlaceholderError` — names are global, so pick one
that reads as yours.

## Verifying

```python
from plinta.utils import Context, resolve_values
resolve_values({"id__in": "__MY_WATCHLIST__"}, Context(user=some_user))
```

An unregistered token is returned **unchanged**, not blanked — blanking would
silently widen the filter. `plinta.utils.unresolved(values)` reports which
tokens in a config have no provider.

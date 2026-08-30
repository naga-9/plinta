---
name: add-date-range
description: Register a named relative date range that resolves to a Q over a date field — current_fiscal_year, last_30_days. Use when a filter bar should offer a date window that core does not ship.
---

# Add a date range

A range is a named date window that a filter bar offers as a choice, and that
resolves to a `Q` over **whichever date field it is given**.

Core ships seven: `past`, `current_month`, `next_month`, `next_2_months`,
`next_3_months`, `next_6_months`, `next_12_months`.

## When to use this

- a window core does not ship — a fiscal year, a rolling 30 days, a sprint
- the window depends on a calendar core must not know about

Use a **placeholder** instead when you need a single value rather than a
window: `__CURRENT_FISCAL_YEAR__` returns `2026`, where a range returns a `Q`.

## Steps

1. Put the resolver in `ranges.py` in your app.

```python
from django.db.models import Q
from plinta.dates import register_range

@register_range("current_fiscal_year", "Current Fiscal Year")
def current_fiscal_year(field, today):
    start, end = fiscal_bounds(today)
    return Q(**{f"{field}__gte": start, f"{field}__lte": end})
```

2. Import it from `AppConfig.ready()`.

3. It appears in every filter bar that offers relative dates. Nothing else to wire.

## The contract

| | |
|---|---|
| Name | lowercase `[a-z][a-z0-9_]*` — it is stored in configuration |
| Label | what a filter bar shows; free text |
| Signature | `fn(field, today) -> Q` |
| `field` | the column being filtered, possibly traversed (`purchase_order__order_date`) |
| `today` | passed in, never called inside — so the range is testable at any date |

## Rules

**Use the field you are given.** Build lookups with `Q(**{f"{field}__gte": …})`,
never a hardcoded column. One range then serves every date column on every model.

**Never call `date.today()` inside the resolver.** It arrives as `today`. A
resolver that reads the clock cannot be tested and behaves differently in a
scheduled report run at midnight.

**Registering twice raises.** `RangeError`.

## Verifying

```python
from datetime import date
from plinta.dates import resolve_q, registered

resolve_q("sale_date", "current_fiscal_year", date(2026, 8, 15))
[(r.name, r.label) for r in registered()]
```

Several names OR together: `resolve_q("expected_date", ["past", "current_month"])`.
An unknown name is ignored; when nothing matches, the result is `None`, which
means *no date filter* rather than *match nothing*.

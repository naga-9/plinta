"""Named relative date ranges, resolved against today.

A filter declares a date field and one or more range names; neither the filter
nor its caller computes dates. Contrib packages register their own — a fiscal
calendar belongs to a legal entity, not to core.
"""
from __future__ import annotations

import calendar
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date

from django.db.models import Q

Resolver = Callable[[str, date], Q]


@dataclass(frozen=True)
class Range:
    """A registered range: a name, the label a filter UI offers, a resolver."""

    name: str
    label: str
    resolve: Resolver


_registry: dict[str, Range] = {}


class RangeError(Exception):
    """A range was registered twice, or under an unusable name."""


def register_range(name: str, label: str, resolve: Resolver) -> Range:
    """Register a range.

    Raises:
        RangeError: the name is already taken.
    """
    if name in _registry:
        raise RangeError(f"{name!r} is already registered")
    _registry[name] = Range(name=name, label=label, resolve=resolve)
    return _registry[name]


def options() -> list[Range]:
    """Every registered range, in registration order, for a filter UI."""
    return list(_registry.values())


def resolve_q(field: str, names: str | Iterable[str], today: date | None = None) -> Q | None:
    """OR the named ranges into one ``Q`` over ``field``.

    Unregistered names are ignored. Returns None when nothing matched, which
    means "no date filter" rather than "match nothing".
    """
    if today is None:
        today = date.today()
    if isinstance(names, str):
        names = [names]

    combined: Q | None = None
    for name in names:
        entry = _registry.get(name)
        if entry is None:
            continue
        q = entry.resolve(field, today)
        combined = q if combined is None else combined | q
    return combined


def month_start(d: date) -> date:
    return d.replace(day=1)


def month_end(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def add_months(d: date, n: int) -> date:
    """First day of the month ``n`` months after ``d``'s month."""
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def _past(field: str, today: date) -> Q:
    return Q(**{f"{field}__lt": today})


def _current_month(field: str, today: date) -> Q:
    return Q(**{f"{field}__gte": month_start(today), f"{field}__lte": month_end(today)})


def _next_months(count: int) -> Resolver:
    """The ``count`` calendar months after the current one."""

    def resolve(field: str, today: date) -> Q:
        return Q(
            **{
                f"{field}__gte": add_months(today, 1),
                f"{field}__lte": month_end(add_months(today, count)),
            }
        )

    return resolve


def register_defaults() -> None:
    """Register core's seven ranges. Idempotent."""
    if "past" in _registry:
        return
    register_range("past", "Past", _past)
    register_range("current_month", "Current Month", _current_month)
    for count, label in ((1, "Next Month"), (2, "Next 2 Months"), (3, "Next 3 Months"),
                         (6, "Next 6 Months"), (12, "Next 12 Months")):
        name = "next_month" if count == 1 else f"next_{count}_months"
        register_range(name, label, _next_months(count))


register_defaults()

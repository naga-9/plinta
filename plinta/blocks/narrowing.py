"""The two narrowings a Block applies to what the viewer sees.

Both are chosen by whoever built the screen, not by the viewer — which is what
separates them from a page filter.

`base_filter` is locked filter values, always applied and never shown.
`queryset_modifier` is a registered callable. Neither may widen: they run over
a queryset `datasources` has already narrowed by row policy, and a wider result
would be rows the viewer may not see.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from django.db.models import QuerySet

if TYPE_CHECKING:
    from plinta.blocks.models import Block

#: A narrowing: a queryset in, a narrower queryset out.
Narrow = Callable[[QuerySet], QuerySet]


def resolved_filter(block: Block, user) -> dict[str, Any]:
    """The block's ``base_filter`` with its placeholders resolved for ``user``.

    A token nothing registered is left as written, so an unknown ``__ME__``
    filters on the literal string and finds nothing, rather than dropping the
    clause and showing every row.
    """
    from plinta.utils.placeholders import Context, resolve_values

    return resolve_values(block.base_filter or {}, Context(user=user))


def apply_base_filter(queryset: QuerySet, block: Block, user) -> QuerySet:
    """Apply the block's locked filter values."""
    values = resolved_filter(block, user)
    return queryset.filter(**values) if values else queryset


def apply_modifier(queryset: QuerySet, block: Block, user) -> QuerySet:
    """Run the block's registered queryset modifier, if it names one.

    An unregistered name raises rather than rendering: a modifier is there to
    hide rows, and skipping a missing one would show every row it was meant to
    exclude.
    """
    from plinta.datasources.modifiers import apply_modifier as run

    if not block.queryset_modifier:
        return queryset
    return run(block.queryset_modifier, queryset, user)


def narrowing_for(block: Block, user) -> Narrow:
    """The narrowing this block applies, as one callable.

    Handed to a component so it can apply it after `datasources` has filtered,
    without learning what a Block is.
    """

    def narrow(queryset: QuerySet) -> QuerySet:
        return apply_modifier(apply_base_filter(queryset, block, user), block, user)

    return narrow

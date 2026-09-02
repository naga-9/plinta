"""Saving a page's filters, so a question worth asking twice is asked once.

The same species as a `SavedView` — user-owned, shareable, `owner = None`
meaning public, the same policy, the same two field permissions behind sharing
and defaulting (§6.1b). Written through the pipeline for the same reason, and
so publishing is a change to `owner` rather than a check somebody wrote.

**One difference, and it is deliberate.** A saved view stores a *delta* over
its block's config, so a change the author makes later reaches every view that
did not override that setting. A filter set stores its values **whole**.

A view's settings are presentation, where inheriting a later change is
usually what somebody wants. Filter values are answers to questions, and an
absent one means *no filter* — which is a real answer, not a missing one. So
"the filters I saved" cannot be told from "the filters I left alone" in a
delta, and a page's defaults changing under a saved set would silently change
what it asks. Whole is the honest shape, for the same reason a list of columns
is pinned.
"""
from __future__ import annotations

from typing import Any

from plinta.pages.models import FilterSet


def visible_sets(page, user) -> list[FilterSet]:
    """The sets on ``page`` this viewer may see: theirs, and the public ones."""
    from plinta.permissions import allowed

    return list(allowed(user, "view", page.filter_sets.all()))


def may_publish(user) -> bool:
    """Whether this viewer may make a set everyone sees.

    For **drawing** the control. The pipeline enforces it, because publishing
    is a change to `owner` and that field has a permission.
    """
    return user.has_perm("plinta_pages.change_filterset_owner")


def may_default(user) -> bool:
    """Whether this viewer may mark a set as the one to open on."""
    return user.has_perm("plinta_pages.change_filterset_is_default")


def declared(page) -> set[str]:
    """The filters this page exposes, which is what a set may hold.

    A value for anything else is dropped rather than stored: the bar is what
    the page offers, and a query string is not — the same rule `filter_q`
    applies when reading them.
    """
    from plinta.pages.rendering import controls_of

    return {control.field_name for control in controls_of(page)}


def kept(page, values: dict[str, Any]) -> dict[str, Any]:
    """``values`` narrowed to what this page declares, blanks dropped.

    A blank is not a filter. Stored, it would be a set that says "no answer"
    where the page's own default might otherwise apply, which is a different
    thing from having no opinion.
    """
    offered = declared(page)
    return {
        name: value
        for name, value in (values or {}).items()
        if name in offered and value not in (None, "", [])
    }


def save(
    page,
    user,
    *,
    name: str,
    values: dict[str, Any],
    filter_set: FilterSet | None = None,
    public: bool = False,
    default: bool = False,
) -> FilterSet:
    """Create or update a filter set on ``page``.

    Through the write pipeline, so the permissions are the ones every write
    uses and a field is asked about only when it **changes** — which is what
    makes publishing ask for `change_filterset_owner` and saving an ordinary
    set ask for nothing extra.

    Raises:
        WriteDenied: the viewer may not make this change.
        ValidationError: the model refused it — a duplicate name, say.
    """
    from plinta.blocks.write import write

    instance = filter_set or FilterSet(page=page, owner=user)
    changing: dict[str, Any] = {"name": name, "values": kept(page, values)}
    if public != (instance.owner_id is None):
        changing["owner"] = None if public else user
    if default != instance.is_default:
        changing["is_default"] = default

    saved, _ = write(instance, changing, user, source="filter bar")
    return saved

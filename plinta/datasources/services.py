"""The three functions every layer above this one reads data through.

Each takes the requesting user, and none has an unfiltered path. Narrowing
happens here once, so nothing above can widen it — a block, a page, an export
and the API all inherit the same filtering because they all arrive through
these.
"""
from __future__ import annotations

from django.db.models import CharField, Q, QuerySet, TextField

from plinta.datasources import prefetch
from plinta.datasources.models import DataSource, DataSourceField
from plinta.permissions import allowed, fields as permitted_fields

#: Field classes a text search can match against.
TEXT_FIELDS = (CharField, TextField)


class DataSourceUnavailable(Exception):
    """The DataSource names a model whose app is no longer installed."""


def _require_user(user) -> None:
    """No unfiltered path, and no system user.

    A default of None would make omitting the argument return every row rather
    than fail, which is the difference between a bug and a leak.
    """
    if user is None:
        raise TypeError("a user is required; there is no unfiltered path")


def _model(datasource: DataSource):
    model = datasource.model
    if model is None:
        raise DataSourceUnavailable(
            f"{datasource.name!r} names {datasource.content_type.app_label}."
            f"{datasource.content_type.model}, whose app is not installed"
        )
    return model


def get_queryset(
    datasource: DataSource, user, *, columns: list[str] | None = None
) -> QuerySet:
    """The rows of ``datasource`` this user may view, with the joins they need.

    ``columns`` names what will be read. Left unset it means every column this
    user may view, so the default is the optimised one — a caller cannot lose
    the joins by forgetting to ask for them, which is how five of v1's nine
    components ended up issuing a query per row.

    Pass an explicit list to narrow it, or ``[]`` for rows with no joins at all.
    """
    _require_user(user)
    model = _model(datasource)
    rows = allowed(user, "view", model._default_manager.all())
    if columns is None:
        columns = [f.field_name for f in get_available_fields(datasource, user)]
    return prefetch.apply(rows, columns)


def get_available_fields(datasource: DataSource, user) -> list[DataSourceField]:
    """The columns of ``datasource`` this user may view, in display order.

    A column with no minted permission is absent rather than allowed: a
    reverse accessor or property nobody declared is denied (§5.7).
    """
    _require_user(user)
    model = _model(datasource)
    granted = permitted_fields(user, "view", model)
    return [f for f in datasource.fields.all() if f.field_name in granted]


def editable_fields(datasource: DataSource, user) -> list[DataSourceField]:
    """The columns this user may change — declared editable *and* granted."""
    _require_user(user)
    model = _model(datasource)
    granted = permitted_fields(user, "change", model)
    return [f for f in datasource.fields.all() if f.editable and f.field_name in granted]


def resolve_path(model, path: str):
    """The Django field a column path points at, or None.

    Follows a traversal like ``region__name``. Returns None for a reverse
    accessor, a property, an annotation, or a path that does not resolve —
    all of which are legitimate columns and none of which is a model field.
    """
    parts = path.split("__")
    current = model
    for i, part in enumerate(parts):
        try:
            field = current._meta.get_field(part)
        except Exception:
            return None
        if i == len(parts) - 1:
            return field
        related = getattr(field, "related_model", None)
        if related is None:
            return None
        current = related
    return None


def searchable_fields(datasource: DataSource, user) -> list[DataSourceField]:
    """The columns a text search may match on.

    Visible columns the user may view, narrowed to those resolving to a text
    field. Searching a column the user cannot see would leak whether a record
    matches — presence rather than content, but an oracle either way, and an
    invisible one.
    """
    model = _model(datasource)
    return [
        f
        for f in get_available_fields(datasource, user)
        if f.visible and isinstance(resolve_path(model, f.field_name), TEXT_FIELDS)
    ]


def search_q(datasource: DataSource, user, term: str) -> Q | None:
    """A ``Q`` matching ``term`` across the columns this user may search.

    A ``Q`` rather than a queryset, so a caller composes it: a header filter
    ANDs it with what is already applied, a picker uses it alone.

    Returns None when the term is empty or nothing is searchable — meaning *no
    text filter*, not *no rows*.
    """
    _require_user(user)
    term = (term or "").strip()
    if not term:
        return None

    combined: Q | None = None
    for field in searchable_fields(datasource, user):
        for path in _search_paths(field):
            clause = Q(**{f"{path}__icontains": term})
            combined = clause if combined is None else combined | clause
    return combined


def _search_paths(field: DataSourceField) -> list[str]:
    """Which paths a column searches on.

    Its own, plus anything named in ``filter_display_format`` — a column
    showing ``{region__name}`` should match on what it displays, not on the id
    behind it.
    """
    paths = [field.field_name]
    if field.filter_display_format:
        import re

        paths += [p for p in re.findall(r"\{([\w__]+)\}", field.filter_display_format)]
    return list(dict.fromkeys(paths))

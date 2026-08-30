"""What must be true at boot for a configured screen to render anything.

Both checks belong here rather than in `permissions`, because both need to
enumerate DataSources and that layer cannot import one (§20.3).
"""
from __future__ import annotations

from django.core.checks import Error, Warning, register


def _rows():
    """Every column, with its DataSource and model, or None if unreadable.

    Checks run before `migrate` on a fresh database, and failing there would
    block the migration that fixes it.
    """
    from django.db import DatabaseError

    from plinta.datasources.models import DataSourceField

    try:
        return list(
            DataSourceField.objects.select_related("data_source__content_type")
        )
    except DatabaseError:
        return None


def _resolves(model, path: str) -> bool:
    """Whether this column name means anything on the model at all.

    A model field or a traversal resolves; so does a reverse accessor or a
    property, both legitimate columns. What is left is a name that must be a
    registered annotation, or nothing will ever produce a value for it.
    """
    from plinta.datasources.services import resolve_path

    if resolve_path(model, path) is not None:
        return True
    root = path.split("__")[0]
    return hasattr(model, root)


@register()
def check_columns_resolve(app_configs=None, **kwargs) -> list[Error]:
    """Every column is a model path, an attribute, or a registered annotation.

    A column that is none of the three renders as nothing with no indication
    why: the queryset simply never gains the annotation.
    """
    from plinta.datasources import annotations

    rows = _rows()
    if rows is None:
        return []

    errors = []
    for field in rows:
        model = field.data_source.model
        if model is None:
            continue  # the app is uninstalled; that is the next check's business
        name = field.field_name
        if _resolves(model, name) or annotations.is_annotation(name):
            continue
        known = ", ".join(sorted(annotations.registered())) or "none"
        errors.append(
            Error(
                f"{field.data_source.name}.{name} is neither a field of "
                f"{model.__name__} nor a registered annotation — the column "
                f"will render as nothing.",
                hint=f"Register it with @register_annotation, or correct the "
                f"name. Registered: {known}.",
                id="plinta.datasources.E001",
                obj=field,
            )
        )
    return errors


@register()
def check_datasource_models_have_a_policy(app_configs=None, **kwargs) -> list[Warning]:
    """Report a DataSource-backed model with no registered policy.

    Informational, not an error: row-level control is opt-in and most models
    never need it. But the absence fails open — every row this user may view by
    model permission is a row the screen shows — so it is reported rather than
    assumed deliberate.
    """
    from django.db import DatabaseError

    from plinta.datasources.models import DataSource
    from plinta.permissions.policies import policy_for

    try:
        sources = list(DataSource.objects.select_related("content_type"))
    except DatabaseError:
        return []

    return [
        Warning(
            f"{ds.name} shows {ds.model.__name__} rows with no registered "
            f"policy — every row the model permission admits is visible.",
            hint="Register a policy, or ignore this if that is intended.",
            id="plinta.datasources.W001",
            obj=ds,
        )
        for ds in sources
        if ds.model is not None and policy_for(ds.model) is None
    ]

"""What must be true at boot for a column to draw.

This check needs both a `DataSourceField` and the renderer registry, so it
belongs to this layer — `datasources` cannot see the registry.
"""
from __future__ import annotations

from django.core.checks import Error, register


@register()
def check_field_renderers_exist(app_configs=None, **kwargs) -> list[Error]:
    """Every column naming a field renderer names one that is registered.

    A column drawing through a missing renderer raises on render, one row into
    the page, and the joins it declared were never applied either.
    """
    from django.db import DatabaseError

    from plinta.datasources.models import DataSourceField
    from plinta.renderers.fields import is_field_renderer, registered

    try:
        columns = list(
            DataSourceField.objects.exclude(renderer="").select_related("data_source")
        )
    except DatabaseError:
        # Checks run before migrate on a fresh database. Nothing to validate
        # against yet, and failing here would block the migration that fixes it.
        return []

    known = ", ".join(sorted(registered())) or "none"
    return [
        Error(
            f"{column.data_source.name}.{column.field_name} draws with "
            f"{column.renderer!r}, which no field renderer matches.",
            hint=f"Register it with @register_field_renderer, or clear the "
            f"column's renderer. Registered: {known}.",
            id="plinta.renderers.E001",
            obj=column,
        )
        for column in columns
        if not is_field_renderer(column.renderer)
    ]

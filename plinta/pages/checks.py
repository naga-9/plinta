"""What must be true at boot for a page's stored filter values to mean anything.

The same shape as the block check, over the three dicts this layer stores: a
filter's default, a saved set's values, and a viewer's remembered state.
"""
from __future__ import annotations

from django.core.checks import Error, register


@register()
def check_filter_placeholders(app_configs=None, **kwargs) -> list[Error]:
    """Every token in a stored filter value names a registered placeholder.

    A token with no provider is left verbatim, so it matches nothing and the
    page shows an empty screen with no indication why.
    """
    from django.db import DatabaseError

    from plinta.pages.models import FilterSet, PageFilter, PageFilterPreference
    from plinta.utils.placeholders import registered, unresolved

    try:
        sources = [
            (f"{f.page.name}: filter {f.label}", {f.field_name: f.default_value}, f)
            for f in PageFilter.objects.exclude(default_value=None).select_related("page")
        ] + [
            (f"{s.page.name}: filter set {s.name}", s.values, s)
            for s in FilterSet.objects.exclude(values={}).select_related("page")
        ] + [
            (f"{p.page.name}: remembered filters", p.values, p)
            for p in PageFilterPreference.objects.exclude(values={}).select_related("page")
        ]
    except DatabaseError:
        # Checks run before migrate on a fresh database. Nothing to validate
        # against yet, and failing here would block the migration that fixes it.
        return []

    known = ", ".join(sorted(registered())) or "none"
    errors = []
    for where, values, obj in sources:
        tokens = unresolved(values or {})
        if tokens:
            errors.append(
                Error(
                    f"{where} names {', '.join(sorted(tokens))}, which nothing "
                    f"registered — the filter will match no rows.",
                    hint=f"Register it with @register_placeholder, or correct "
                    f"the token. Registered: {known}.",
                    id="plinta.pages.E001",
                    obj=obj,
                )
            )
    return errors

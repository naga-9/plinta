"""What must be true at boot for a block's stored filters to mean anything.

`utils` holds the placeholder registry but cannot read a Block, so this layer
owes the check.
"""
from __future__ import annotations

from django.core.checks import Error, register


@register()
def check_capability_templates(app_configs=None, **kwargs) -> list[Error]:
    """Every registered capability names a template that can be loaded.

    A capability declares where its section is drawn, and the declaration is
    only checked when something draws it — which may be months after the typo,
    on the one screen that uses it. Reads no rows, so it raises normally.
    """
    from django.template import TemplateDoesNotExist
    from django.template.loader import get_template

    from plinta.blocks.capabilities import registered

    errors = []
    for capability in registered():
        if not capability.template:
            continue
        try:
            get_template(capability.template)
        except TemplateDoesNotExist:
            errors.append(
                Error(
                    f"capability {capability.name!r} draws with "
                    f"{capability.template!r}, which no loader can find.",
                    hint="Ship the template with the app that registers the "
                    "capability, or correct the path.",
                    id="plinta.blocks.E002",
                )
            )
    return errors


@register()
def check_base_filter_placeholders(app_configs=None, **kwargs) -> list[Error]:
    """Every token in a `base_filter` names a registered placeholder.

    A token with no provider is left in the filter verbatim, so it matches
    nothing and the block renders empty with no indication why. Blanking it
    instead would widen the filter, which is the worse failure and is why the
    resolver leaves it — that choice is what makes this check necessary.
    """
    from django.db import DatabaseError

    from plinta.blocks.models import Block
    from plinta.utils.placeholders import registered, unresolved

    try:
        blocks = list(Block.objects.exclude(base_filter={}))
    except DatabaseError:
        # Checks run before migrate on a fresh database. Nothing to validate
        # against yet, and failing here would block the migration that fixes it.
        return []

    known = ", ".join(sorted(registered())) or "none"
    errors = []
    for block in blocks:
        tokens = unresolved(block.base_filter)
        if tokens:
            errors.append(
                Error(
                    f"{block.name}'s base_filter names "
                    f"{', '.join(sorted(tokens))}, which nothing registered — "
                    f"the filter will match no rows.",
                    hint=f"Register it with @register_placeholder, or correct "
                    f"the token. Registered: {known}.",
                    id="plinta.blocks.E001",
                    obj=block,
                )
            )
    return errors

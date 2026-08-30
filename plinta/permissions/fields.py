"""Field permissions: one per column, per action.

A field permission gates a **column**, so these are minted from whatever
declares columns — never from the model's own fields, which would produce
permissions for things nobody displays and none for the reverse accessors,
properties and computed columns that are displayed.

This module takes a model and field names. It never learns what declares them,
which is what lets the layer that does sit above it.
"""
from __future__ import annotations

from django.db.models import Model

# Models are imported inside each function, never at module scope: a library
# that imports models at import time breaks anything loaded while the app
# registry is still populating, and cannot be imported before django.setup().

#: Actions a column can carry. A computed column takes ``view`` only.
FIELD_ACTIONS = ("view", "change")

#: Django's own limit on ``Permission.codename``.
CODENAME_MAX_LENGTH = 100


class FieldPermissionError(Exception):
    """A codename would not fit, or a rename collided with an existing one."""


def codename(action: str, model: type[Model], field_name: str) -> str:
    """``view`` + ``Book`` + ``price`` -> ``view_book_price``.

    Without the app label, which Django stores separately on the content type.
    """
    name = f"{action}_{model._meta.model_name}_{field_name}"
    if len(name) > CODENAME_MAX_LENGTH:
        raise FieldPermissionError(
            f"{name!r} is {len(name)} characters; the limit is {CODENAME_MAX_LENGTH}"
        )
    return name


def _label(action: str, model: type[Model], field_name: str) -> str:
    return f"Can {action} {model._meta.verbose_name} {field_name}"


def sync_field(model: type[Model], field_name: str, *, editable: bool = False) -> None:
    """Ensure this column's permissions match ``editable``.

    ``view`` always exists. ``change`` exists only while the column is
    editable, so toggling it off removes the permission rather than leaving a
    grant that no longer means anything.

    Idempotent: safe to call for a column that already has them.
    """
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(model)
    Permission.objects.get_or_create(
        content_type=ct,
        codename=codename("view", model, field_name),
        defaults={"name": _label("view", model, field_name)},
    )
    change = codename("change", model, field_name)
    if editable:
        Permission.objects.get_or_create(
            content_type=ct,
            codename=change,
            defaults={"name": _label("change", model, field_name)},
        )
    else:
        Permission.objects.filter(content_type=ct, codename=change).delete()


def rename_field(model: type[Model], old_name: str, new_name: str) -> int:
    """Rename a column's permissions **in place**, so grants survive.

    ``auth_user_user_permissions`` points at a permission's primary key, so
    deleting and recreating would drop every grant on the column silently.

    Returns the number of permissions renamed.

    Raises:
        FieldPermissionError: the new name already has a permission.
    """
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    if old_name == new_name:
        return 0
    ct = ContentType.objects.get_for_model(model)
    clashes = Permission.objects.filter(
        content_type=ct,
        codename__in=[codename(a, model, new_name) for a in FIELD_ACTIONS],
    )
    if clashes.exists():
        raise FieldPermissionError(
            f"{model.__name__}.{new_name} already has "
            f"{sorted(clashes.values_list('codename', flat=True))}"
        )

    renamed = 0
    for action in FIELD_ACTIONS:
        renamed += Permission.objects.filter(
            content_type=ct, codename=codename(action, model, old_name)
        ).update(
            codename=codename(action, model, new_name),
            name=_label(action, model, new_name),
        )
    return renamed


def remove_field(model: type[Model], field_name: str) -> int:
    """Delete a column's permissions. Returns how many were removed."""
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(model)
    deleted, _ = Permission.objects.filter(
        content_type=ct,
        codename__in=[codename(a, model, field_name) for a in FIELD_ACTIONS],
    ).delete()
    return deleted


def sync_model(model: type[Model], fields: dict[str, bool]) -> None:
    """Make ``model``'s field permissions match ``fields`` exactly.

    ``fields`` maps a column name to whether it is editable. Columns absent
    from it lose their permissions.

    The idempotent backstop for paths that do not fire per-row signals —
    a bulk import, or anything that has drifted.
    """
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    for field_name, editable in fields.items():
        sync_field(model, field_name, editable=editable)

    ct = ContentType.objects.get_for_model(model)
    keep = {codename(a, model, f) for f in fields for a in FIELD_ACTIONS}
    stale = [
        perm.pk
        for perm in Permission.objects.filter(content_type=ct)
        if _is_field_permission(perm.codename, model) and perm.codename not in keep
    ]
    Permission.objects.filter(pk__in=stale).delete()


def _is_field_permission(name: str, model: type[Model]) -> bool:
    """Whether a codename is one of ours, rather than Django's own ``view_book``."""
    return any(
        name.startswith(f"{action}_{model._meta.model_name}_") for action in FIELD_ACTIONS
    )


def minted_fields(action: str, model: type[Model]) -> set[str]:
    """Every column of ``model`` that has a permission for ``action``.

    Read from Django's permission table, so a layer can learn which columns are
    declared without importing the layer that declares them.
    """
    from django.contrib.auth.models import Permission

    prefix = f"{action}_{model._meta.model_name}_"
    return {
        perm.codename[len(prefix):]
        for perm in Permission.objects.filter(
            content_type__app_label=model._meta.app_label, codename__startswith=prefix
        )
    }

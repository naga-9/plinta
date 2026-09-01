"""The one path by which plinta mutates a consumer's data.

Every mutation goes through it, so the permission checks, the validation and
the events are stated once instead of at each call site.

The stage order carries the safety properties:

1. authorise — model permission, row policy, then field permission per field
2. coerce and validate — through the model layer, never around it
3. emit ``object_writing``
4. save, then apply M2M
5. compute ``changes``
6. emit ``object_written``

Authorisation is first, so nothing is validated or written for a user who may
not write it. The save is before M2M because a many-to-many needs a pk.
"""
from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Model

from plinta.events import signals
from plinta.permissions import can, fields as permitted_fields


class WriteDenied(Exception):
    """The user may not perform this write.

    Carries what was refused, so a caller can say which field rather than
    only that something was refused.
    """

    def __init__(self, message: str, *, denied_fields: list[str] | None = None):
        self.denied_fields = denied_fields or []
        super().__init__(message)


def _m2m_names(model: type[Model]) -> set[str]:
    return {f.name for f in model._meta.many_to_many}


def _m2m_value(instance: Model, name: str) -> list[Any]:
    """A many-to-many's current members, as pks, in a stable order."""
    return sorted(getattr(instance, name).values_list("pk", flat=True))


def authorise(user, action: str, instance: Model, fields: list[str]) -> None:
    """Refuse the write before anything is validated or saved.

    Both permission tiers first — the model permission and the row policy —
    then the field permission for each field being written. A field the user
    may not change is refused rather than dropped: silently ignoring half a
    write would tell the caller it succeeded.

    Raises:
        WriteDenied: the row or one of the fields is not writable.
    """
    if not can(user, action, instance):
        raise WriteDenied(f"may not {action} this {type(instance).__name__}")

    if not fields:
        return
    granted = permitted_fields(user, "change", type(instance))
    denied = sorted(set(fields) - granted - _m2m_names(type(instance)))
    if denied:
        raise WriteDenied(
            f"may not change {', '.join(denied)}", denied_fields=denied
        )


def _before(instance: Model, fields: list[str], m2m: set[str]) -> dict[str, Any]:
    """The values a saved row holds now, for the diff.

    Read from the database rather than the in-memory instance, which already
    carries the new values by the time this runs.
    """
    if instance.pk is None:
        return {}
    stored = type(instance)._default_manager.filter(pk=instance.pk).first()
    if stored is None:
        return {}
    return {
        name: _m2m_value(stored, name) if name in m2m else getattr(stored, name, None)
        for name in fields
    }


@transaction.atomic
def write(
    instance: Model,
    values: dict[str, Any],
    user,
    *,
    source: str = "",
) -> tuple[Model, dict[str, tuple[Any, Any]]]:
    """Apply ``values`` to ``instance`` and save it.

    Returns the saved row and ``{field: (before, after)}``. The row is always
    returned, so a caller never has to ask for it separately — an inline edit
    can refresh a column the database derived.

    Args:
        instance: unsaved for a create, loaded for an update.
        values: the fields being written, model fields and many-to-many alike.
        user: the writer. Both permission tiers and every field are checked.
        source: what performed the write, carried on both events.

    Raises:
        WriteDenied: the user may not write this row or one of these fields.
        ValidationError: the model layer refused the values.
    """
    model = type(instance)
    creating = instance.pk is None
    mode = "create" if creating else "update"
    m2m = _m2m_names(model) & set(values)
    plain = {name: value for name, value in values.items() if name not in m2m}

    authorise(user, "add" if creating else "change", instance, list(values))

    before = _before(instance, list(values), m2m)

    for name, value in plain.items():
        try:
            setattr(instance, name, value)
        except (ValueError, TypeError) as exc:
            # Assigning a relation something that is not one raises here,
            # before any validation runs — so without this a viewer typing
            # into the wrong box gets a 500 rather than being told which
            # field they got wrong. A value the field cannot hold is a
            # rejection like any other.
            raise ValidationError({name: [str(exc)]}) from exc
    # Through the model layer, never around it: full_clean runs the field
    # validators, the model's own clean, and its constraints.
    instance.full_clean(exclude=[f.name for f in model._meta.many_to_many])

    signals.emit_writing(
        instance, mode=mode, fields=sorted(values), actor=user, source=source
    )

    instance.save()
    # After the save, because a many-to-many needs a pk to point at.
    for name in m2m:
        getattr(instance, name).set(values[name])

    changes = {}
    for name in sorted(values):
        after = _m2m_value(instance, name) if name in m2m else getattr(instance, name, None)
        was = before.get(name)
        if creating or was != after:
            changes[name] = (was, after)

    signals.emit_written(
        instance, mode=mode, changes=changes, actor=user, source=source
    )
    return instance, changes


@transaction.atomic
def delete(instance: Model, user, *, source: str = "") -> None:
    """Delete ``instance``, having checked that this user may.

    The pk is read before the delete and carried on the event, because
    Django's collector clears it on the instance it deleted.

    Raises:
        WriteDenied: the user may not delete this row.
    """
    if not can(user, "delete", instance):
        raise WriteDenied(f"may not delete this {type(instance).__name__}")

    pk = instance.pk
    instance.delete()
    signals.emit_deleted(instance, pk=pk, actor=user, source=source)


def write_or_errors(
    instance: Model, values: dict[str, Any], user, *, source: str = ""
) -> tuple[Model | None, dict[str, list[str]] | None]:
    """``write``, with a model's validation errors returned rather than raised.

    For the endpoints, which answer a rejected write with a field-keyed body
    rather than a traceback. A `WriteDenied` still raises: refusing a write is
    not the same answer as failing to validate one.
    """
    try:
        saved, _ = write(instance, values, user, source=source)
    except ValidationError as exc:
        return None, exc.message_dict
    return saved, None

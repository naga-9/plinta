"""Permissions follow the columns.

``permissions`` owns the minting; this layer owns the trigger, because it is
the one that knows a column exists. Nothing here decides policy — it only
notices a change and calls down.
"""
from __future__ import annotations

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from plinta.datasources.models import DataSource, DataSourceField

#: Where ``pre_save`` leaves the stored ``field_name`` for ``post_save``.
OLD_NAME = "_plinta_old_field_name"


def _model_of(field: DataSourceField):
    """The Django model a column belongs to, or None if its app has gone."""
    return field.data_source.model


@receiver(pre_save, sender=DataSourceField)
def remember_old_field_name(sender, instance, **kwargs):
    """Stash the stored name so ``post_save`` can tell a rename from an edit.

    ``post_save`` sees only the new value, the row being already written, so
    without this a rename is indistinguishable from a new column and every
    grant on it is dropped.
    """
    if not instance.pk:
        setattr(instance, OLD_NAME, None)
        return
    setattr(
        instance,
        OLD_NAME,
        DataSourceField.objects.filter(pk=instance.pk)
        .values_list("field_name", flat=True)
        .first(),
    )


@receiver(post_save, sender=DataSourceField)
def sync_field_permissions(sender, instance, created, **kwargs):
    """Mint, rename or re-scope this column's permissions."""
    from plinta.permissions.fields import rename_field, sync_field

    model = _model_of(instance)
    if model is None:
        return

    old = getattr(instance, OLD_NAME, None)
    if old and old != instance.field_name:
        rename_field(model, old, instance.field_name)
    sync_field(model, instance.field_name, editable=instance.editable)
    setattr(instance, OLD_NAME, instance.field_name)


@receiver(post_delete, sender=DataSourceField)
def remove_field_permissions(sender, instance, **kwargs):
    """Drop a removed column's permissions.

    Unconditional, because a model has exactly one DataSource — no other
    screen can still be showing this column.
    """
    from plinta.permissions.fields import remove_field

    model = _model_of(instance)
    if model is not None:
        remove_field(model, instance.field_name)


@receiver(post_save, sender=DataSource)
def mint_registered_actions(sender, instance, created, **kwargs):
    """Give a newly registered model every action's permission.

    Django mints add/change/delete/view itself; anything else — ``export``,
    ``import`` — exists only because something registered it, and a model
    registered after that would otherwise never get one.
    """
    from plinta.permissions.actions import mint_for

    if not created:
        return
    model = instance.model
    if model is not None:
        mint_for(model)

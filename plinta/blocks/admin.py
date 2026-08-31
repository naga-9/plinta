"""Blocks and saved views in Django's admin.

The Blocks catalogue and the block inspector (§12.2, §12.3) are the editors
built for this; these registrations are the generic fallback every Django app
provides, and they ship here so no consumer writes them twice.

`config` shows as raw JSON. Its shape belongs to the component, and deriving a
real form from that schema is what the inspector does.
"""
from django.contrib import admin

from plinta.blocks.models import Block, SavedView


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("name", "component_type", "data_source", "mode")
    list_filter = ("component_type", "mode")
    search_fields = ("name", "description")
    autocomplete_fields = ("data_source",)


@admin.register(SavedView)
class SavedViewAdmin(admin.ModelAdmin):
    """A viewer's own arrangement of a block.

    Owned rows, so the admin shows everybody's — a policy narrows the plinta
    screens, never this one.
    """

    list_display = ("name", "block", "owner", "is_default")
    list_filter = ("is_default",)
    search_fields = ("name",)
    autocomplete_fields = ("block", "owner")

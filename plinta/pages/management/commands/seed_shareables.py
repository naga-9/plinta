"""Register plinta's own shareable models, so their `owner` can be gated.

Not a screen. A DataSource over one of plinta's own models exists because a
**field** on it needs a permission, and `DataSourceField` rows are the only
thing that mints one (§6.1b) — the screen, if there ever is one, is
incidental.

`FilterSet` and `SavedView` are the two: user-owned, shareable, `owner = None`
meaning public. Publishing one is a change to that single field, so without
these rows `change_filterset_owner` and `change_savedview_owner` do not exist
and any owner may publish to everyone unchecked.

The configuration models — Block, Page, DataSource itself — are deliberately
absent. They are edited through the authoring screens (§12) and gated whole
rather than field by field.

Idempotent, like every seeder (§13.2).
"""
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from plinta.blocks.models import SavedView
from plinta.datasources.models import DataSource, DataSourceField
from plinta.pages.models import FilterSet

#: `owner` is the column this exists for. The rest are declared so the model
#: is legible if somebody does put a screen on it, and because a column with
#: no DSF row cannot be shown at all.
SHAREABLES = [
    (
        SavedView,
        "saved_views",
        "Saved views",
        [
            ("name", "Name", {"editable": True}),
            # What the view actually holds. Written through the pipeline like
            # any other field, so it needs a permission like any other field.
            ("config", "Settings", {"editable": True}),
            ("block", "Block", {}),
            # The one that matters: `change_savedview_owner` gates whether
            # somebody may publish a view to everyone.
            ("owner", "Owner", {"editable": True}),
            ("is_default", "Default", {"editable": True}),
        ],
    ),
    (
        FilterSet,
        "filter_sets",
        "Filter sets",
        [
            ("name", "Name", {"editable": True}),
            ("values", "Values", {"editable": True}),
            ("page", "Page", {}),
            ("owner", "Owner", {"editable": True}),
            ("is_default", "Default", {"editable": True}),
        ],
    ),
]


class Command(BaseCommand):
    help = "Register FilterSet and SavedView as DataSources. Idempotent."

    @transaction.atomic
    def handle(self, *args, **options):
        for model, name, label, columns in SHAREABLES:
            source, _ = DataSource.objects.update_or_create(
                content_type=ContentType.objects.get_for_model(model),
                defaults={"name": name, "label": label},
            )
            for order, (field_name, field_label, extra) in enumerate(columns):
                # Saving a DataSourceField is what mints its permissions; the
                # signal does it, so there is nothing to sync afterwards.
                DataSourceField.objects.update_or_create(
                    data_source=source,
                    field_name=field_name,
                    defaults={"label": field_label, "order": order, **extra},
                )
            self.stdout.write(f"{label}: {len(columns)} columns")

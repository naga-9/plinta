"""Create the screen that reads the trail.

A `Page`, not a view: an audit log is a table of rows with filters, which is
exactly what a page of blocks is for. So it appears in the menu through the
ordinary permission-filtered path (§9.5) and disappears when this app is
uninstalled, with nothing in core to remove.

Idempotent.
"""
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from plinta.blocks.models import Block
from plinta.datasources.models import DataSource, DataSourceField, Format
from plinta.pages.models import Lookup, MenuGroup, MenuSection, Page, PageBlock, PageFilter

from plinta.contrib.audit.models import AuditEntry

COLUMNS = [
    ("at", "When", {"format": Format.DATETIME, "sorter": "date"}),
    ("action", "Action", {"filterable": True}),
    ("target_label", "Record", {"filterable": True}),
    ("actor__username", "By", {"filterable": True}),
    ("source", "Source", {}),
]


class Command(BaseCommand):
    help = "Create the audit page. Idempotent."

    @transaction.atomic
    def handle(self, *args, **options):
        source, _ = DataSource.objects.update_or_create(
            name="audit_entries",
            defaults={
                "label": "Audit trail",
                "content_type": ContentType.objects.get_for_model(AuditEntry),
            },
        )
        for order, (name, label, options_) in enumerate(COLUMNS):
            DataSourceField.objects.update_or_create(
                data_source=source,
                field_name=name,
                defaults={"label": label, "order": order, **options_},
            )

        block, _ = Block.objects.update_or_create(
            name="audit-trail",
            owner=None,
            defaults={
                "component_type": "table_plinta",
                "data_source": source,
                "config": {
                    "title": "Audit trail",
                    "page_size": 50,
                    "sort": [{"field": "at", "direction": "desc"}],
                    "empty_text": "Nothing has been recorded yet.",
                },
            },
        )

        section, _ = MenuSection.objects.get_or_create(
            name="Administration", defaults={"order": 90}
        )
        group, _ = MenuGroup.objects.get_or_create(
            section=section, name="Records", defaults={"order": 10}
        )
        page, _ = Page.objects.update_or_create(
            slug="audit-trail",
            owner=None,
            defaults={
                "name": "Audit trail",
                "description": "Every write, and who made it.",
                "menu_group": group,
                "menu_order": 10,
            },
        )
        PageBlock.objects.update_or_create(
            page=page, block=block,
            defaults={"column": 0, "row": 0, "width": 12, "height": 8, "order": 0},
        )
        for order, (field, label, lookup) in enumerate(
            [("target_label", "Record contains", Lookup.ICONTAINS),
             ("action", "Action", Lookup.EXACT)]
        ):
            PageFilter.objects.update_or_create(
                page=page, field_name=field,
                defaults={"label": label, "lookup": lookup, "order": order},
            )

        self.stdout.write(f"audit page ready at {page.get_absolute_url()}")

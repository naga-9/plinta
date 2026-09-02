"""The screen that lists what somebody has been told.

The app already ships two ways in — a bell in the topbar and a preferences
screen — and neither is a list. This is the list, and it is a `Page` rather
than a view for the reason every contrib screen is: it reaches the menu
through the ordinary permission-filtered path and goes away with the package,
leaving core nothing to clean up (§13.2).

**No policy is written here, because the app already has one.** A
`Notification` is `Owner("recipient")`, so this page shows a person their own
and nobody else's without the page knowing that. Registering a DataSource
never widens access — the row policy and the field permissions decide, and
both were decided already.

Idempotent.
"""
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from plinta.blocks.models import Block
from plinta.datasources.models import DataSource, DataSourceField, Format
from plinta.pages.models import Lookup, MenuGroup, MenuSection, Page, PageBlock, PageFilter

from plinta.contrib.notifications.models import Notification

COLUMNS = [
    ("created_at", "When", {"format": Format.DATETIME, "sorter": "date"}),
    ("title", "What", {"filterable": True}),
    ("kind", "Kind", {"filterable": True}),
    ("body", "Detail", {"format": Format.TEXTAREA}),
    # Null until it is read, which is what makes "unread" a filter rather
    # than a second column of booleans.
    ("read_at", "Read", {"format": Format.DATETIME, "sorter": "date"}),
]


class Command(BaseCommand):
    help = "Create the notifications page. Idempotent."

    @transaction.atomic
    def handle(self, *args, **options):
        source, _ = DataSource.objects.update_or_create(
            name="notifications",
            defaults={
                "label": "Notifications",
                "content_type": ContentType.objects.get_for_model(Notification),
                "description": "What you have been told.",
            },
        )
        for order, (name, label, options_) in enumerate(COLUMNS):
            DataSourceField.objects.update_or_create(
                data_source=source,
                field_name=name,
                defaults={"label": label, "order": order * 10, **options_},
            )

        block, _ = Block.objects.update_or_create(
            name="my-notifications",
            owner=None,
            defaults={
                "component_type": "table_plinta",
                "data_source": source,
                "config": {
                    "page_size": 25,
                    "sort": [{"field": "created_at", "direction": "desc"}],
                    "empty_text": "Nothing has been sent to you.",
                },
            },
        )

        section, _ = MenuSection.objects.get_or_create(
            name="Administration", defaults={"order": 90}
        )
        group, _ = MenuGroup.objects.get_or_create(
            section=section, name="Me", defaults={"order": 50}
        )
        page, _ = Page.objects.update_or_create(
            slug="notifications",
            owner=None,
            defaults={
                "name": "Notifications",
                "description": "Everything you have been sent.",
                "menu_group": group,
                "menu_order": 10,
            },
        )
        PageBlock.objects.update_or_create(
            page=page,
            block=block,
            defaults={"column": 0, "row": 0, "width": 12, "height": 8,
                      "order": 0, "title": "Sent to you"},
        )
        for order, (field, label, lookup) in enumerate(
            [("title", "Contains", Lookup.ICONTAINS),
             ("kind", "Kind", Lookup.EXACT)]
        ):
            PageFilter.objects.update_or_create(
                page=page,
                field_name=field,
                defaults={"label": label, "lookup": lookup, "order": order},
            )

        self.stdout.write(f"notifications page ready at {page.get_absolute_url()}")

"""The screen that lists people.

Core's, because `accounts` dissolves and nothing else owns the user model
(ADR 0002, §13.2). The consumer supplies the model through
`AUTH_USER_MODEL`; this registers it as a DataSource so its columns carry
field permissions like any other model's.

**`password` is not a column, and that is the point.** A `DataSourceField` is
the only thing that mints a field permission (§5.7), so declaring one over
`password` would create `view_user_password` and make the hash something a
screen could be configured to show. Columns absent from this list cannot be
shown at all, which is the safest thing absence has ever bought us.

Idempotent.
"""
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from plinta.blocks.models import Block
from plinta.datasources.models import DataSource, DataSourceField, Format
from plinta.pages.models import Lookup, MenuGroup, MenuSection, Page, PageBlock, PageFilter

#: What a screen may show about a person. Deliberately short: every entry here
#: mints two permissions, and a column nobody needs is a permission somebody
#: has to reason about.
COLUMNS = [
    ("username", "Username", {"filterable": True, "editable": True}),
    ("first_name", "First name", {"filterable": True, "editable": True}),
    ("last_name", "Last name", {"filterable": True, "editable": True}),
    ("email", "Email", {"filterable": True, "editable": True}),
    ("is_active", "Active", {"filterable": True, "editable": True}),
    # Read-only on purpose. Staff and superuser decide who reaches Django's
    # admin, and granting that from a dashboard cell is not a thing a
    # dashboard cell should do.
    ("is_staff", "Staff", {"filterable": True}),
    ("last_login", "Last seen", {"format": Format.DATETIME, "sorter": "date"}),
    ("date_joined", "Joined", {"format": Format.DATE, "sorter": "date"}),
]


class Command(BaseCommand):
    help = "Create the users page. Idempotent."

    @transaction.atomic
    def handle(self, *args, **options):
        model = get_user_model()
        source, _ = DataSource.objects.update_or_create(
            name="users",
            defaults={
                "label": "Users",
                "content_type": ContentType.objects.get_for_model(model),
                "description": "The people who sign in.",
            },
        )
        for order, (name, label, options_) in enumerate(COLUMNS):
            DataSourceField.objects.update_or_create(
                data_source=source,
                field_name=name,
                defaults={"label": label, "order": order * 10, **options_},
            )

        block, _ = Block.objects.update_or_create(
            name="users",
            owner=None,
            defaults={
                "component_type": "table_plinta",
                "data_source": source,
                "config": {
                    "page_size": 25,
                    "sort": [{"field": "username", "direction": "asc"}],
                    "empty_text": "Nobody has an account yet.",
                },
            },
        )

        section, _ = MenuSection.objects.get_or_create(
            name="Administration", defaults={"order": 90}
        )
        group, _ = MenuGroup.objects.get_or_create(
            section=section, name="People", defaults={"order": 30}
        )
        page, _ = Page.objects.update_or_create(
            slug="users",
            owner=None,
            defaults={
                "name": "Users",
                "description": "Who can sign in, and what they are called.",
                "menu_group": group,
                "menu_order": 10,
            },
        )
        PageBlock.objects.update_or_create(
            page=page,
            block=block,
            defaults={"column": 0, "row": 0, "width": 12, "height": 8,
                      "order": 0, "title": "People"},
        )
        for order, (field, label, lookup) in enumerate(
            [("username", "Username contains", Lookup.ICONTAINS),
             ("is_active", "Active", Lookup.EXACT)]
        ):
            PageFilter.objects.update_or_create(
                page=page,
                field_name=field,
                defaults={"label": label, "lookup": lookup, "order": order},
            )

        self.stdout.write(f"users page ready at {page.get_absolute_url()}")

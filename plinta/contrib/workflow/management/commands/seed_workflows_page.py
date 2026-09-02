"""The screen that lists the workflows defined on this installation.

A workflow's definition is **configuration, not data** — knowing that an order
can move from open to closed tells you nothing about any order — which is why
the app's policy is `AllowAll` on view and the model permission is the whole
question. So this page needs no narrowing of its own.

Two blocks, because a workflow is only legible with its states beside it: the
definitions, and every state across all of them. Transitions are deliberately
not a third — a table of from/to pairs reads as noise next to the states, and
the workflow's own screen is where a transition belongs.

Idempotent.
"""
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from plinta.blocks.models import Block
from plinta.datasources.models import DataSource, DataSourceField
from plinta.pages.models import Lookup, MenuGroup, MenuSection, Page, PageBlock, PageFilter

from plinta.contrib.workflow.models import Workflow, WorkflowState

WORKFLOW_COLUMNS = [
    ("name", "Workflow", {"filterable": True}),
    ("code", "Code", {"filterable": True}),
    # What it governs. A traversal, which is an ordinary column path — the
    # DataSource does not care that it crosses a relation (§6.2).
    ("content_type__app_label", "App", {"filterable": True}),
    ("content_type__model", "Model", {"filterable": True}),
    ("state_field", "State field", {}),
    ("is_active", "Active", {"filterable": True}),
]

STATE_COLUMNS = [
    ("workflow__name", "Workflow", {"filterable": True}),
    ("order", "Order", {"sorter": "number"}),
    ("label", "State", {"filterable": True}),
    ("code", "Code", {}),
    ("is_initial", "Initial", {}),
    ("is_final", "Final", {}),
]


class Command(BaseCommand):
    help = "Create the workflows page. Idempotent."

    @transaction.atomic
    def handle(self, *args, **options):
        workflows = self.source(
            Workflow, "workflows", "Workflows", "What each model may do.",
            WORKFLOW_COLUMNS,
        )
        states = self.source(
            WorkflowState, "workflow_states", "Workflow states",
            "Every state, across every workflow.", STATE_COLUMNS,
        )

        definitions, _ = Block.objects.update_or_create(
            name="workflow-definitions",
            owner=None,
            defaults={
                "component_type": "table_plinta",
                "data_source": workflows,
                "config": {
                    "page_size": 25,
                    "sort": [{"field": "name", "direction": "asc"}],
                    "empty_text": "No workflow is defined.",
                },
            },
        )
        state_list, _ = Block.objects.update_or_create(
            name="workflow-states",
            owner=None,
            defaults={
                "component_type": "table_plinta",
                "data_source": states,
                "config": {
                    "page_size": 50,
                    "sort": [
                        {"field": "workflow__name", "direction": "asc"},
                        {"field": "order", "direction": "asc"},
                    ],
                    "empty_text": "No states are defined.",
                },
            },
        )

        section, _ = MenuSection.objects.get_or_create(
            name="Administration", defaults={"order": 90}
        )
        group, _ = MenuGroup.objects.get_or_create(
            section=section, name="System", defaults={"order": 40}
        )
        page, _ = Page.objects.update_or_create(
            slug="workflows",
            owner=None,
            defaults={
                "name": "Workflows",
                "description": "The states each model moves through.",
                "menu_group": group,
                "menu_order": 20,
            },
        )
        PageBlock.objects.update_or_create(
            page=page, block=definitions,
            defaults={"column": 0, "row": 0, "width": 12, "height": 6,
                      "order": 0, "title": "Defined workflows"},
        )
        PageBlock.objects.update_or_create(
            page=page, block=state_list,
            defaults={"column": 0, "row": 6, "width": 12, "height": 8,
                      "order": 1, "title": "States"},
        )
        PageFilter.objects.update_or_create(
            page=page, field_name="name",
            defaults={"label": "Workflow contains", "lookup": Lookup.ICONTAINS,
                      "order": 0},
        )

        self.stdout.write(f"workflows page ready at {page.get_absolute_url()}")

    def source(self, model, name, label, description, columns):
        source, _ = DataSource.objects.update_or_create(
            name=name,
            defaults={
                "label": label,
                "content_type": ContentType.objects.get_for_model(model),
                "description": description,
            },
        )
        for order, (field, field_label, options) in enumerate(columns):
            DataSourceField.objects.update_or_create(
                data_source=source,
                field_name=field,
                defaults={"label": field_label, "order": order * 10, **options},
            )
        return source

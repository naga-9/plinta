"""Workflows, their states and their transitions, in Django's admin.

States and transitions are data, so this is where a workflow is built.

**Saving a transition mints its permission**, and renaming a state renames the
permissions in place rather than recreating them — a grant points at a
permission's primary key, so recreating one would drop every grant on it
silently.
"""
from django.contrib import admin

from plinta.contrib.workflow.models import Workflow, WorkflowState, WorkflowTransition


class WorkflowStateInline(admin.TabularInline):
    model = WorkflowState
    extra = 0
    ordering = ("order",)


@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    """A workflow binds to a model by content type and names its state column.

    Nothing inherits from this app: the column is the consumer's own.
    """

    list_display = ("code", "name", "content_type", "state_field", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    inlines = [WorkflowStateInline]


@admin.register(WorkflowState)
class WorkflowStateAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "workflow", "order", "is_initial", "is_final")
    list_filter = ("workflow", "is_initial", "is_final")
    search_fields = ("code", "label")
    ordering = ("workflow", "order")


@admin.register(WorkflowTransition)
class WorkflowTransitionAdmin(admin.ModelAdmin):
    """Each row is one grantable permission, and one optional guard.

    The guard is a registered name, never an import path, so this field cannot
    point at arbitrary code.
    """

    list_display = ("workflow", "label", "from_state", "to_state", "guard", "order")
    list_filter = ("workflow",)
    ordering = ("workflow", "order")
    autocomplete_fields = ("from_state", "to_state")

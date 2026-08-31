"""The audit trail in Django's admin.

Read-only throughout: an audit entry that can be edited is not an audit trail.
Deleting is left to a retention job, not a person with a mouse.
"""
from django.contrib import admin

from plinta.contrib.audit.models import AuditEntry


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = ("at", "action", "actor", "content_type", "object_id")
    list_filter = ("action", "content_type")
    search_fields = ("object_repr",)
    date_hierarchy = "at"
    readonly_fields = [f.name for f in AuditEntry._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

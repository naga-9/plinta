"""Notifications, the email queue and per-user preferences, in the admin.

The queue is the useful one: a channel that enqueues rather than posts means a
notification that never arrived is visible here as a row that never sent.
"""
from django.contrib import admin

from plinta.contrib.notifications.models import (
    Notification,
    NotificationPreference,
    QueuedEmail,
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "kind", "created_at", "read_at")
    list_filter = ("kind", "created_at")
    search_fields = ("title", "body")
    date_hierarchy = "created_at"
    autocomplete_fields = ("recipient",)


@admin.register(QueuedEmail)
class QueuedEmailAdmin(admin.ModelAdmin):
    list_display = ("subject", "to", "status", "attempts", "queued_at", "sent_at")
    list_filter = ("status",)
    search_fields = ("subject", "to")
    date_hierarchy = "queued_at"


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """One row per person, kind and channel."""

    list_display = ("user", "kind", "channel", "enabled")
    list_filter = ("channel", "enabled")
    autocomplete_fields = ("user",)

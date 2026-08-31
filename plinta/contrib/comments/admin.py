"""Comments in Django's admin.

Threads nest to any depth, so the list shows each comment's parent rather than
trying to draw the tree — the record's own screen is where a thread reads.
"""
from django.contrib import admin

from plinta.contrib.comments.models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("author", "posted_at", "content_type", "object_id", "reply_to")
    list_filter = ("content_type", "posted_at")
    search_fields = ("body",)
    date_hierarchy = "posted_at"
    autocomplete_fields = ("author", "reply_to")

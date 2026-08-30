"""The comments app."""
from django.apps import AppConfig


class CommentsConfig(AppConfig):
    name = "plinta.contrib.comments"
    label = "plinta_comments"
    verbose_name = "plinta comments"
    default_auto_field = "django.db.models.BigAutoField"

    requires = ["plinta.events", "plinta.permissions", "plinta.blocks"]

    def ready(self):
        from plinta.contrib.comments import capabilities, policies  # noqa: F401

        capabilities.register()

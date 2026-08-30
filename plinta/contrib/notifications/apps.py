"""The notifications app."""
from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = "plinta.contrib.notifications"
    label = "plinta_notifications"
    verbose_name = "plinta notifications"
    default_auto_field = "django.db.models.BigAutoField"

    #: The listener needs only these. The bell and the preference screen add
    #: `datasources`, `blocks` and `pages` when they land (§13).
    requires = ["plinta.events", "plinta.permissions"]

    def ready(self):
        from plinta.contrib.notifications import listeners, policies  # noqa: F401

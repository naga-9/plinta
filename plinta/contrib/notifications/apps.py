"""The notifications app."""
from django.apps import AppConfig

from plinta.shell.links import register_shell_link
from plinta.shell.topbar import register_topbar_item


class NotificationsConfig(AppConfig):
    name = "plinta.contrib.notifications"
    label = "plinta_notifications"
    verbose_name = "plinta notifications"
    default_auto_field = "django.db.models.BigAutoField"

    requires = ["plinta.events", "plinta.permissions", "plinta.shell"]

    def ready(self):
        from plinta.contrib.notifications import (  # noqa: F401
            builtin_channels,
            listeners,
            policies,
        )

        builtin_channels.register()

        # The shell draws whatever is registered and names no package, so the
        # bell is contributed rather than built in (§10.1).
        register_topbar_item(
            "notifications",
            template="plinta/notifications/bell.html",
            permission="plinta_notifications.view_notification",
            order=10,
        )
        register_shell_link(
            "notification_preferences",
            "Notifications",
            url_name="notifications:preferences",
            permission="plinta_notifications.view_notification",
            order=500,
        )

"""The audit app."""
from django.apps import AppConfig


class AuditConfig(AppConfig):
    name = "plinta.contrib.audit"
    label = "plinta_audit"
    verbose_name = "plinta audit"
    default_auto_field = "django.db.models.BigAutoField"

    #: The listener needs permissions; `seed_audit_page` needs the rest. The
    #: event bus is not listed: `plinta.events` is a plain package, always
    #: importable and impossible to omit.
    requires = [
        "plinta.permissions",
        "plinta.datasources",
        "plinta.blocks",
        "plinta.pages",
    ]

    def ready(self):
        # Imported for its side effect: connecting the receivers. This is the
        # whole of the app's coupling to the rest of plinta — five signals it
        # does not own, and nothing that knows it is listening.
        from plinta.contrib.audit import listeners, policies  # noqa: F401

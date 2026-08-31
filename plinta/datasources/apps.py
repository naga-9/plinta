"""The datasources app."""
from django.apps import AppConfig


class DataSourcesConfig(AppConfig):
    name = "plinta.datasources"
    label = "plinta_datasources"
    verbose_name = "plinta data sources"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # The declared-dependency checks, registered wherever plinta is.
        from plinta.utils import checks as _dependency_checks  # noqa: F401
        # Imported for their side effects: connecting the receivers that keep
        # field permissions in step with the columns, and registering the
        # boot checks.
        from plinta.datasources import checks, signals  # noqa: F401

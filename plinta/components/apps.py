"""The components app."""
from django.apps import AppConfig


class ComponentsConfig(AppConfig):
    name = "plinta.components"
    label = "plinta_components"
    verbose_name = "plinta components"

    def ready(self):
        # The declared-dependency checks, registered wherever plinta is.
        from plinta.utils import checks as _dependency_checks  # noqa: F401
        # Imported for its side effect: registering the table component.
        from plinta.components import table  # noqa: F401

"""The renderers app."""
from django.apps import AppConfig


class RenderersConfig(AppConfig):
    name = "plinta.renderers"
    label = "plinta_renderers"
    verbose_name = "plinta renderers"

    def ready(self):
        # The declared-dependency checks, registered wherever plinta is.
        from plinta.utils import checks as _dependency_checks  # noqa: F401
        # Imported for their side effects: registering the HTML renderer and
        # the boot check.
        from plinta.renderers import checks, html  # noqa: F401

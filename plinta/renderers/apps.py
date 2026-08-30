"""The renderers app."""
from django.apps import AppConfig


class RenderersConfig(AppConfig):
    name = "plinta.renderers"
    label = "plinta_renderers"
    verbose_name = "plinta renderers"

    def ready(self):
        # Imported for its side effect: registering the boot check.
        from plinta.renderers import checks  # noqa: F401

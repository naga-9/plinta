"""The shell app."""
from django.apps import AppConfig


class ShellConfig(AppConfig):
    name = "plinta.shell"
    label = "plinta_shell"
    verbose_name = "plinta shell"

    def ready(self):
        # Imported for its side effect: registering the boot checks.
        from plinta.shell import checks  # noqa: F401

"""The blocks app."""
from django.apps import AppConfig


class BlocksConfig(AppConfig):
    name = "plinta.blocks"
    label = "plinta_blocks"
    verbose_name = "plinta blocks"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # The declared-dependency checks, registered wherever plinta is.
        from plinta.utils import checks as _dependency_checks  # noqa: F401
        # Imported for their side effects: registering the policies that make
        # blocks and saved views shareable, and the boot check.
        from plinta.blocks import checks, policies  # noqa: F401

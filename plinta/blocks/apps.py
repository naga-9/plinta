"""The blocks app."""
from django.apps import AppConfig


class BlocksConfig(AppConfig):
    name = "plinta.blocks"
    label = "plinta_blocks"
    verbose_name = "plinta blocks"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Imported for its side effect: registering the policies that make
        # blocks and saved views shareable.
        from plinta.blocks import policies  # noqa: F401

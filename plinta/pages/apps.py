"""The pages app."""
from django.apps import AppConfig


class PagesConfig(AppConfig):
    name = "plinta.pages"
    label = "plinta_pages"
    verbose_name = "plinta pages"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Imported for their side effects: registering the policies that make
        # pages and filter sets shareable, and the boot check.
        from plinta.pages import checks, policies  # noqa: F401

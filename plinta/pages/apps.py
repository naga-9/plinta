"""The pages app."""
from django.apps import AppConfig


class PagesConfig(AppConfig):
    name = "plinta.pages"
    label = "plinta_pages"
    verbose_name = "plinta pages"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # The declared-dependency checks, registered wherever plinta is.
        from plinta.utils import checks as _dependency_checks  # noqa: F401
        # Imported for their side effects: registering the policies that make
        # pages and filter sets shareable, and the boot check.
        from plinta.pages import checks, placeholders, policies, widgets  # noqa: F401

        placeholders.register()
        widgets.register_defaults()

        # Core's own page action: arranging the cards by dragging them. It
        # asks for the permission the positions endpoint checks, and is
        # absent where there is no grid — a detail page, a custom template —
        # rather than present and refusing (§12.4).
        from plinta.pages.actions import register_page_action
        from plinta.pages.models import PageType

        register_page_action(
            "composer",
            template="plinta/pages/edit_layout.html",
            permission="plinta_pages.change_pageblock",
            page_types=(PageType.DASHBOARD,),
            order=20,
        )

"""The composer app.

Core stores a placement's four integers and owns the rule that writes them
(`pages/composition.py`). This app supplies the dragging, and nothing else —
which is why uninstalling it leaves a page composer that still works, with
numbers typed instead of dragged (§12.4).

It ships no models, so it has no migrations and no permissions of its own. It
asks for `plinta_pages.change_pageblock`, which is the permission core already
checks when the drag posts.
"""
from django.apps import AppConfig

from plinta.pages.actions import register_page_action
from plinta.utils.assets import register_script, register_stylesheet


class ComposerConfig(AppConfig):
    name = "plinta.contrib.composer"
    label = "plinta_composer"
    verbose_name = "plinta composer"

    requires = ["plinta.pages", "plinta.shell"]

    def ready(self):
        # Imported here, not at module scope: `ready()` runs during app
        # loading, and a model import at the top of this file is a circular
        # import waiting to happen.
        from plinta.pages.models import PageType

        register_stylesheet("composer/css/composer.css", order=200)
        register_script("composer/js/composer.js", order=200)
        register_page_action(
            "composer",
            template="composer/edit_layout.html",
            permission="plinta_pages.change_pageblock",
            # A dashboard has a grid; a detail page and a custom template do
            # not, so the control is absent there rather than inert.
            page_types=(PageType.DASHBOARD,),
            order=20,
        )

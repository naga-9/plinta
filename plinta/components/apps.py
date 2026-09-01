"""The components app."""
from django.apps import AppConfig


class ComponentsConfig(AppConfig):
    name = "plinta.components"
    label = "plinta_components"
    verbose_name = "plinta components"

    def ready(self):
        # The declared-dependency checks, registered wherever plinta is.
        from plinta.utils import checks as _dependency_checks  # noqa: F401
        # Imported for their side effect: registering core's two components,
        # one per contract — the table reads, the form writes (ADR 0005).
        from plinta.components import checks as _layout_checks  # noqa: F401
        from plinta.components import form, table  # noqa: F401
        from plinta.utils.assets import register_script

        # After core's client, which it registers with. Ordered below the
        # contrib range so a package's adapter still lands after it.
        register_script("plinta/js/form.js", order=200)

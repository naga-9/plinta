"""An interactive table, drawn by Tabulator."""
from django.apps import AppConfig


class TableTabulatorConfig(AppConfig):
    name = "plinta.contrib.components.table_tabulator"
    label = "plinta_table_tabulator"
    verbose_name = "plinta components: Tabulator table"

    #: A component and its assets. No models, no events.
    requires = ["plinta.blocks", "plinta.shell"]

    def ready(self):
        from plinta.contrib.components.table_tabulator import component  # noqa: F401
        from plinta.utils.assets import register_script, register_stylesheet

        # Vendored, not fetched: an install must work offline and under a
        # strict CSP, and no deployment should depend on a CDN (§17.1).
        register_stylesheet("plinta/tabulator/tabulator_simple.min.css", order=300)
        # Ours, after the vendor's: it styles the mount, not the grid.
        register_stylesheet("plinta/tabulator/tabulator.css", order=301)
        register_script("plinta/tabulator/tabulator.min.js", order=300)
        # After the vendor, and after core's client — the adapter registers
        # with one and calls into the other.
        register_script("plinta/tabulator/adapter.js", order=310)

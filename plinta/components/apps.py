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
        register_script("plinta/js/column-order.js", order=200)
        register_script("plinta/js/sort-builder.js", order=200)

        # The one config field no schema can describe: which columns, in what
        # order. Registered on `ComponentConfig`, so every component's config
        # inherits it — `columns` is declared there, and a chooser each author
        # had to re-register is one an author will forget.
        from plinta.components.base import ColumnsConfig
        from plinta.forms.overrides import register_widget

        register_widget(ColumnsConfig, "columns", "plinta/settings/columns.html")

        # And the other setting no annotation can describe: a list of columns
        # and directions, which is a builder rather than the JSON a
        # `list[Sort]` would otherwise become.
        from plinta.components.tabular import TabularConfig

        register_widget(TabularConfig, "sort", "plinta/settings/sort.html")

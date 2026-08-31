"""A multi-select drawn by Tom Select.

Core's own `multiselect_plinta` is chips over a native `<select multiple>` and
carries no vendor. This is the same capability with a vendor behind it, and it
registers through the same door — `capability_implementation`, so
`multiselect_tomselect` sits beside `multiselect_plinta` and neither is
privileged.

Installed by listing this app; chosen per filter by name:

    PageFilter.objects.create(..., widget="multiselect_tomselect")
"""
from django.apps import AppConfig


class FiltersTomSelectConfig(AppConfig):
    name = "plinta.contrib.filters_tomselect"
    label = "plinta_filters_tomselect"
    verbose_name = "plinta filters: Tom Select"

    #: A widget and its assets. No models, no permissions, no events.
    requires = ["plinta.pages", "plinta.shell"]

    def ready(self):
        from plinta.pages.widgets import register_filter_widget
        from plinta.utils.assets import register_script, register_stylesheet

        register_filter_widget(
            "multiselect_tomselect",
            template="plinta/tomselect/multiselect.html",
            label="Multi-select (searching)",
            multiple=True,
            needs_options=True,
        )

        # Vendored, not fetched: an install must work offline and under a
        # strict CSP, and no deployment should depend on a CDN being up (§17).
        register_stylesheet("plinta/tomselect/tom-select.min.css", order=200)
        register_script("plinta/tomselect/tom-select.complete.min.js", order=200)
        # After the vendor, so the glue can rely on `TomSelect` existing.
        register_script("plinta/tomselect/adapter.js", order=210)

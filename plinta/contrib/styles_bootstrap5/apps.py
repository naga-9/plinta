"""Bootstrap 5 class names for plinta's markup."""
from django.apps import AppConfig


class StylesBootstrap5Config(AppConfig):
    name = "plinta.contrib.styles_bootstrap5"
    label = "plinta_styles_bootstrap5"
    verbose_name = "plinta styles: Bootstrap 5"

    #: Class names only. Nothing here reads a model, a permission or an event.
    requires = ["plinta.utils"]

    def ready(self):
        from plinta.contrib.styles_bootstrap5 import pack

        pack.register()

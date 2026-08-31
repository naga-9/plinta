"""Bootstrap 5 class names for plinta's markup."""
from django.apps import AppConfig


class StylesBootstrap5Config(AppConfig):
    name = "plinta.contrib.styles_bootstrap5"
    label = "plinta_styles_bootstrap5"
    verbose_name = "plinta styles: Bootstrap 5"

    #: Nothing. A mapping needs no application installed — `plinta.utils`,
    #: which holds the registry, is a plain package that is always importable.

    def ready(self):
        from plinta.contrib.styles_bootstrap5 import pack

        pack.register()

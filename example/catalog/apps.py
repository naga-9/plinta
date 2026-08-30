"""The catalog app.

Registers everything from `ready()`, which is the one place plinta asks a
consumer to use (§18.14).
"""
from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = "catalog"
    verbose_name = "Bookshop catalogue"

    #: Declared, and checked at boot: catalog cannot work without these.
    requires = [
        "plinta.permissions",
        "plinta.datasources",
        "plinta.blocks",
        "plinta.pages",
        "plinta.shell",
    ]

    def ready(self):
        from catalog import plinta_registrations as registrations

        registrations.register_policies()
        registrations.connect_listeners()
        registrations.register_links()

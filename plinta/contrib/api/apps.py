"""The API app.

Contrib, not core (§15.1). A machine-to-machine API is not required to turn
models into screens, so it fails the sentence test — and a project that does
not want one does not mount it and does not carry the key table.
"""
from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = "plinta.contrib.api"
    label = "plinta_api"
    verbose_name = "plinta API"
    default_auto_field = "django.db.models.BigAutoField"

    requires = ["plinta.datasources", "plinta.blocks", "plinta.permissions"]

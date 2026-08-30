"""The permissions app. No models — it exists to register system checks."""
from django.apps import AppConfig


class PermissionsConfig(AppConfig):
    name = "plinta.permissions"
    label = "plinta_permissions"
    verbose_name = "plinta permissions"

    def ready(self):
        from plinta.permissions import checks  # noqa: F401

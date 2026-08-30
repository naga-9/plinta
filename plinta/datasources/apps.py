"""The datasources app."""
from django.apps import AppConfig


class DataSourcesConfig(AppConfig):
    name = "plinta.datasources"
    label = "plinta_datasources"
    verbose_name = "plinta data sources"
    default_auto_field = "django.db.models.BigAutoField"

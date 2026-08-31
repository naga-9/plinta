"""DataSources in Django's admin.

Registered here because this app owns the models. The Data Sources screen
(§12.1) is a domain-specific editor on top of the generic one, not a
replacement for it — and only this app can spare every consumer from writing
these registrations themselves.

Not permission-aware: the admin answers to `is_staff` and the model
permission, and knows nothing of policies. That is true of the admin for every
Django app, and it is why the plinta screens exist.
"""
from django.contrib import admin

from plinta.datasources.models import DataSource, DataSourceField


class DataSourceFieldInline(admin.TabularInline):
    """The columns a screen may use.

    A column exists because it is listed here — it is not every model field —
    and saving one mints that column's permissions, so adding a row is a
    permission change.
    """

    model = DataSourceField
    extra = 0
    fields = ("field_name", "label", "order", "visible", "format", "renderer")
    ordering = ("order",)


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "label", "content_type")
    search_fields = ("name", "label")
    inlines = [DataSourceFieldInline]


@admin.register(DataSourceField)
class DataSourceFieldAdmin(admin.ModelAdmin):
    list_display = ("field_name", "label", "data_source", "order", "visible")
    list_filter = ("visible", "format", "data_source")
    search_fields = ("field_name", "label")
    ordering = ("data_source", "order")

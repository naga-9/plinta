"""The model registry: which models plinta may show, and how their columns behave."""
from __future__ import annotations

from django.core.validators import RegexValidator
from django.db import models

NAME_VALIDATOR = RegexValidator(
    regex=r"^[a-z][a-z0-9_]*$",
    message="Must start with a lowercase letter and contain only lowercase letters, "
    "numbers and underscores.",
)


class Sorter(models.TextChoices):
    STRING = "string", "String"
    NUMBER = "number", "Number"
    DATE = "date", "Date"


class HeaderFilter(models.TextChoices):
    NONE = "", "None"
    INPUT = "input", "Text input"
    SELECT = "select", "Select"


class Format(models.TextChoices):
    NONE = "", "None"
    CURRENCY = "currency", "Currency"
    PERCENT = "percent", "Percent"
    DATE = "date", "Date"
    DATETIME = "datetime", "Date and time"
    NUMBER = "number", "Number"
    TEXTAREA = "textarea", "Long text"
    HTML = "html", "HTML"


class FilterWidget(models.TextChoices):
    NONE = "", "None"
    MULTISELECT = "multiselect", "Multi-select"
    DATERANGE = "daterange", "Date range"


class FilterLookup(models.TextChoices):
    EXACT = "exact", "Exact"
    IN = "in", "One of"
    RANGE = "range", "Between"


class PickerMode(models.TextChoices):
    """How an editor offers the choices for a related field."""

    AUTO = "auto", "Automatic"
    LIST = "list", "Full list"
    SEARCH = "search", "Search as you type"


class DataSource(models.Model):
    """A Django model plinta may show.

    Registration is data, not a decorator: a row created in the browser or by a
    seeder. Adding a DataSource is configuration; adding the model behind it is
    code.
    """

    name = models.SlugField(
        max_length=100,
        unique=True,
        validators=[NAME_VALIDATOR],
        help_text="Identifier used in configuration, e.g. 'purchase_orders'.",
    )
    label = models.CharField(max_length=200, help_text="Shown to people, e.g. 'Purchase Orders'.")
    description = models.TextField(blank=True)
    content_type = models.OneToOneField(
        "contenttypes.ContentType",
        on_delete=models.PROTECT,
        related_name="datasource",
        help_text="The Django model this represents. One DataSource per model.",
    )
    is_active = models.BooleanField(default=True)
    show_in_api = models.BooleanField(
        default=False,
        help_text="Publish as a resource on the public API. Curation, not access "
        "control — permissions decide what a caller may read either way.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["label"]
        verbose_name = "data source"

    def __str__(self) -> str:
        return self.label

    @property
    def model(self) -> type[models.Model] | None:
        """The Django model class, or None if its app is no longer installed."""
        return self.content_type.model_class()


class DataSourceField(models.Model):
    """One column, and how it behaves.

    A column is not always a model field: ``field_name`` may traverse a
    relation (``region__name``), name a reverse accessor, a property, or a
    registered annotation.
    """

    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name="fields")
    field_name = models.CharField(
        max_length=100,
        help_text="Field path on the model. May traverse, e.g. 'region__name'.",
    )
    label = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)

    # --- display ---
    visible = models.BooleanField(default=True, help_text="Shown by default.")
    format = models.CharField(max_length=20, choices=Format, blank=True, default="")
    width = models.PositiveIntegerField(
        null=True, blank=True, help_text="Fixed pixel width. Unset lets the widget decide."
    )
    decimals = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Decimal places. Honoured by every renderer."
    )
    thousands_separator = models.BooleanField(default=False)
    prefix = models.CharField(
        max_length=8,
        blank=True,
        default="",
        help_text="Drawn before the value, e.g. '$'. Replaces whatever the format "
        "would have drawn.",
    )
    suffix = models.CharField(
        max_length=8,
        blank=True,
        default="",
        help_text="Drawn after the value, e.g. 'kg' or '%'.",
    )

    # --- sorting and filtering ---
    sorter = models.CharField(max_length=10, choices=Sorter, default=Sorter.STRING)
    header_filter = models.CharField(max_length=10, choices=HeaderFilter, blank=True, default="")
    filterable = models.BooleanField(
        default=False, help_text="Offered as a control on a page's filter bar."
    )
    filter_widget = models.CharField(max_length=20, choices=FilterWidget, blank=True, default="")
    filter_lookup = models.CharField(
        max_length=10, choices=FilterLookup, default=FilterLookup.EXACT
    )
    filter_display_format = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Template for a filter's option labels, e.g. '{state__name}'.",
    )

    # --- editing ---
    editable = models.BooleanField(
        default=False, help_text="Mints a change permission for this column."
    )
    picker_mode = models.CharField(
        max_length=10,
        choices=PickerMode,
        default=PickerMode.AUTO,
        help_text="How a related field offers its choices. 'auto' picks a list "
        "under a hundred rows and a search above.",
    )

    class Meta:
        ordering = ["order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["data_source", "field_name"], name="unique_field_per_datasource"
            )
        ]
        verbose_name = "data source field"

    def __str__(self) -> str:
        return f"{self.data_source.name}.{self.field_name}"

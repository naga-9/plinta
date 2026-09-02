"""The forms behind the authoring screens.

Ordinary Django forms, deliberately. `DataSource` and `DataSourceField` are
**configuration** models: they are gated whole rather than field by field
(§6.1b), so there is nothing for the write pipeline's per-field permissions to
check and a `ModelForm` is the honest tool.

That is the same reason `plinta.forms` is not used here either — it derives a
form from a **pydantic schema**, which is what a component's config is. A
model is Django's own subject.
"""
from __future__ import annotations

from django import forms
from django.contrib.contenttypes.models import ContentType

from plinta.blocks.models import Block
from plinta.datasources.models import DataSource, DataSourceField
from plinta.pages.models import Page, PageBlock
from plinta.utils.styles import classes

#: What a column carries beyond its identity. Kept apart in the form so the
#: screen can fold it away: eight of the sixteen options are presentation, and
#: a table showing all of them at once is a wall.
PRESENTATION = (
    "format",
    "width",
    "decimals",
    "thousands_separator",
    "prefix",
    "suffix",
    "renderer",
    "picker_mode",
)


#: Rendered by the formset, but not settings: the primary key the formset uses
#: to match a row, and its delete checkbox. Both are drawn by hand.
PLUMBING = ("id", "DELETE")


def style(form) -> None:
    """Put plinta's own class names on Django's widgets.

    A `ModelForm` renders bare controls, and the shell's stylesheet is written
    against `pl-input` and friends. Read from `classes()` rather than written
    in, so a style pack reaches these screens like every other (§10.3).
    """
    cls = classes()
    for name, field in form.fields.items():
        widget = field.widget
        attrs = widget.attrs
        if isinstance(widget, forms.CheckboxInput):
            attrs["class"] = cls["checkbox"]
        elif isinstance(widget, forms.Select):
            attrs["class"] = cls["select"]
        elif isinstance(widget, forms.Textarea):
            attrs["class"] = cls["textarea"]
        else:
            attrs["class"] = cls["input"]
        if name == "field_name":
            attrs["list"] = "pl-field-paths"


def registerable() -> list[ContentType]:
    """Models that could be registered: everything without a DataSource yet.

    One DataSource per model (§6.1), so a model already registered is not
    offered again — the constraint would refuse it, and a picker that offers
    what cannot be chosen is a control that lies.
    """
    taken = set(DataSource.objects.values_list("content_type_id", flat=True))
    return [
        content_type
        for content_type in ContentType.objects.order_by("app_label", "model")
        if content_type.pk not in taken and content_type.model_class() is not None
    ]


class DataSourceForm(forms.ModelForm):
    """Registering a model, or renaming one that is registered."""

    class Meta:
        model = DataSource
        fields = ["content_type", "name", "label", "description", "is_active",
                  "show_in_api"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self)
        if self.instance.pk:
            # The model a DataSource is about does not change. Field
            # permissions are minted per model, so moving one would orphan
            # every grant on its columns (§5.7).
            self.fields.pop("content_type")
        else:
            self.fields["content_type"].queryset = ContentType.objects.filter(
                pk__in=[c.pk for c in registerable()]
            )


class ColumnForm(forms.ModelForm):
    """One column, with its sixteen options.

    Saving this is what mints, renames or removes its field permissions —
    a signal on the model does it, so nothing here has to remember (§5.7).
    That makes this screen the entry point for the permission surface as much
    as for the column surface.
    """

    class Meta:
        model = DataSourceField
        exclude = ["data_source"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self)


ColumnFormSet = forms.modelformset_factory(
    DataSourceField,
    form=ColumnForm,
    extra=1,
    can_delete=True,
)


def field_paths(model) -> list[str]:
    """The model's own fields, as a hint for somebody adding a column.

    A hint and not a constraint: a column may name a traversal
    (`region__name`), an annotation or a property, none of which appear here
    and all of which are legitimate (§6.2).
    """
    if model is None:
        return []
    return sorted(
        field.name
        for field in model._meta.get_fields()
        if getattr(field, "concrete", False)
    )


def split(formset) -> list[dict]:
    """Each column form, with its fields already sorted into two groups.

    Done here rather than in the template because a template has no way to
    ask a form for "the fields not in this list", and the alternative is a
    filter that exists only to work around that.
    """
    rows = []
    for form in formset.forms:
        rows.append({
            "form": form,
            "identity": [
                form[name]
                for name in form.fields
                if name not in PRESENTATION and name not in PLUMBING
            ],
            "presentation": [
                form[name] for name in PRESENTATION if name in form.fields
            ],
            "delete": form["DELETE"] if "DELETE" in form.fields else None,
        })
    return rows


def component_choices() -> list[tuple[str, str]]:
    """Every registered component, as select options.

    From the registry rather than a list, so a consumer's component appears
    the moment it is registered — the same door core's own go through (§7.1).
    """
    from plinta.components.registry import registered

    return sorted(
        (name, getattr(component, "label", "") or name)
        for name, component in registered().items()
    )


class BlockCreateForm(forms.ModelForm):
    """A new block: what it is, before what it says.

    Only the three fields a block cannot exist without. Everything else is the
    inspector's, because config cannot be edited until the component is known.
    """

    class Meta:
        model = Block
        fields = ["name", "component_type", "data_source"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["component_type"] = forms.ChoiceField(
            choices=component_choices(), label="Component"
        )
        style(self)


class BlockForm(forms.ModelForm):
    """A block's own fields — everything except its config.

    `component_type` is absent: a block's config is validated against its
    component's schema with `extra='forbid'`, so changing the component would
    invalidate every setting at once. Create another block instead.

    `owner` is absent too. Publishing is a decision, not a field, so it is a
    checkbox the view reads — the same shape a saved view uses (§6.1b).
    """

    class Meta:
        model = Block
        fields = ["name", "data_source", "mode", "description", "icon",
                  "queryset_modifier", "base_filter", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self)


class PageForm(forms.ModelForm):
    """A page's own settings: what it is called and where it appears."""

    class Meta:
        model = Page
        fields = ["name", "slug", "description", "page_type", "template_name",
                  "primary_data_source", "context_param", "show_in_menu",
                  "menu_group", "menu_order", "menu_icon", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self)


class PlacementForm(forms.ModelForm):
    """Putting one block on a page.

    Position is absent: it is edited by the grid form, or by dragging when
    `contrib.composer` is installed. Adding a block and arranging it are
    different acts, and one form doing both makes every drag a chance to
    re-point a card at another block.
    """

    class Meta:
        model = PageBlock
        fields = ["block", "title", "tab", "is_visible"]

    def __init__(self, *args, page=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if page is not None and user is not None:
            from plinta.blocks.inspector import visible_blocks

            # A block this viewer cannot see is not one they can place: the
            # picker would otherwise be a way to learn that it exists.
            self.fields["block"].queryset = visible_blocks(user)
        style(self)

---
name: add-widget-override
description: Replace the derived form widget for one field of a config schema with your own template. Use when a config field's type carries no shape — list[dict[str, Any]] and its kind — so the block inspector would otherwise show a JSON textarea.
---

# Add a widget override

The block inspector derives its form from a component's pydantic config
schema. A field annotated `list[dict[str, Any]]` carries no shape, so the only
derivable widget is a JSON textarea — which asks a non-developer to hand-edit
JSON. An override replaces that one widget with your template.

## When to use this

The field is a list of structured objects, or needs an editor a type cannot
express: reordering by drag, a colour picker, a state-to-column mapping.

Do **not** use it for a field a widget already fits. `str`, `int`, `float`,
`bool` and their optional forms derive correctly.

## Steps

1. Type the field as narrowly as the data allows first. A typed sub-model gives
   the engine a repeating sub-form and makes validation real:

```python
class Series(BaseModel):
    field: str
    kind: Literal["bar", "line", "scatter"] = "bar"
    colour: str | None = None

class ChartConfig(BaseModel):
    series: list[Series] = Field(default_factory=list)
```

2. Register the override for what typing still cannot express:

```python
from plinta.forms import register_widget

register_widget(ChartConfig, "series", "chart/series_editor.html")
```

3. Write the template. It receives the `FormField` and must emit an input named
   after the field whose value the schema can validate — normally a hidden JSON
   input populated by JS from a structured UI.

## The contract

| | |
|---|---|
| Signature | `register_widget(schema_class, field_name, template_path)` |
| Keyed by | the schema **class**, not its name |
| Field | must exist on the schema, or it raises at import |
| Effect | sets `FormField.override_template`; `FormField.widget` keeps the derived value as a fallback |

## Rules

**Pass the class, not a string.** A name would orphan every override on a
renamed class, silently — the derived widget returning with no error.

**One override per field.** A second raises `OverrideError`. If two packages
want the same field, one of them is reaching into the other's schema.

**The override is a widget, not a field.** It cannot add, rename or remove
config; the schema still decides what exists and what validates.

## Verifying

```python
from plinta.forms import fields_for, overrides_for
fields_for(ChartConfig, overrides=overrides_for(ChartConfig))
```

The field's `override_template` is your path; every other field still derives.
A misspelled field name raises immediately, naming the fields that do exist.

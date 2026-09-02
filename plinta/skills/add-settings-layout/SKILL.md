---
name: add-settings-layout
description: Arrange your component's settings form — headings, columns, order. Use when the stacked default is not enough for a chart, a gantt or anything with more than a handful of options. Not for changing a control (register a widget) or for a record form (add-form-layout).
---

# Arrange your component's settings

Your component gets a settings form for free: the saved-view editor and the
block inspector both derive it from your `config_schema`, and without a layout
the settings stack in declaration order. **That is fine for most components** —
core's own table registers none. Reach for this when stacking reads badly:
several kinds of setting that want separating, or an order that is not the
order they were declared in.

## The split

**Core owns the mechanisms.** A control that knows something:

| | knows |
|---|---|
| `columns` | which columns this viewer may see, ticked and draggable |
| `sort` | column and direction rows, priority by order |
| `choice` | the values your `Literal` or `Enum` admits |
| `column` | the columns of the block's DataSource, asked for by name |
| `text` `number` `bool` | derived from the annotation |
| *inherit* | a blank control means "same as the block" — every mechanism has this |

**You own the arrangement.** Which settings appear, in what order, under what
headings. Core would arrange a chart, a gantt and a table wrong, so it does not
try.

## Register it

```python
from plinta.forms.layouts import register_config_layout

register_config_layout(ChartConfig, "yourapp/chart_settings.html")
```

Against the **schema**, not a name — a settings form is always about one
schema. Registered on a base schema it reaches every subclass, nearest first.

## Write it

```html
{% load plinta_form %}

<div class="row">
    <div class="col-6">{% setting "x_field" %}</div>
    <div class="col-6">{% setting "y_field" %}</div>
</div>

<fieldset>
    <legend>Appearance</legend>
    {% setting "chart_type" %}
    {% setting "stacked" %}
</fieldset>
```

`{% setting %}` draws the label, the control, the help text, and the block's
value behind it. You place it.

## What you do not write

The form tag, the save, the name field, the sharing controls and the delta.
A layout that owned those could get one subtly wrong and the form would render
perfectly and store the wrong thing. The worst a layout can do is leave a
setting out, which is visible.

## What to expect

**A blank control means "same as the block".** There is no override checkbox —
a scalar shows only its override with the block's value as a placeholder, and
a boolean is a three-state select. If you are writing help text, do not explain
inheritance; the control already says it.

**A container is always stored.** A list has no blank, so `columns`, `sort` and
any `list[…]` of yours are the view's own whatever they hold. That is what
keeps a column added to the DataSource later out of a view saved before it.

**A setting you never place is absent from the form** — and still in the
config. That is a choice your layout makes, so make it on purpose.

**A setting that names a column must ask for the picker.** A string to the
type system is a choice to a person, and derived from `str` it is a text box —
whatever is typed validates and then fails at the query, which is a 500 on
somebody else's screen:

```python
total_field: str = Field(
    default="",
    title="Field to total",
    json_schema_extra={"widget": "column"},
)
```

The annotation cannot carry this, because the columns are not known until a
block names a DataSource. So the field asks for the mechanism and core
supplies one that knows which columns this viewer may see.

**Say which kinds it may name.** A column that will be summed may only be a
number — `"kinds": ["number"]`. Offered a title, `Sum` returns **zero** rather
than failing, and a zero with nothing wrong with it is worse than an error:

```python
json_schema_extra={"widget": "column", "kinds": ["number"]}
```

Kinds are `string`, `number`, `boolean`, `date`, `datetime`, `time`,
`relation`, `relations`. Leave them out and every column is offered, which is
right for something like a link. A **computed** column has no model field, so
its `sorter` is what says which kind it is — one more reason to set it.

**Name your settings in the schema, not the template:**

```python
striped: bool = Field(
    default=False,
    title="Shade alternate rows",
    description="Easier to follow a wide row across.",
)
```

Without a `title` the label is the field name with the underscores taken out,
which reads like a field name. The same titles serve the block inspector.

## Verifying

```python
def test_it_arranges_the_settings(config_layout_registry):
    register_config_layout(ChartConfig, "yourapp/chart_settings.html")
    assert layout_for(ChartConfig) == "yourapp/chart_settings.html"
```

Use the `config_layout_registry` fixture so a test's registration does not
leak.

## Related

- `add-component` — the schema these settings come from
- `add-form-layout` — the same idea for a **record** form

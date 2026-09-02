---
name: add-form-layout
description: Arrange a form block's fields with your own template — columns, fieldsets, a full-width note. Use when the stacked default is not enough. Not for restyling controls (a style pack) or for adding a field (DataSourceField.editable).
---

# Add a form layout

Core's form stacks its fields. Anything else — three across, a full-width note,
a fieldset around two of them — is a template you register and a block names.

## Register it

In your `AppConfig.ready()`:

```python
from plinta.components.layouts import register_form_layout

register_form_layout("book", "catalog/book_form.html")
```

A **key, not a path in the block's config**. A template name stored in a row is
a string in the database deciding what code runs, and plinta refuses that shape
elsewhere for the same reason: `queryset_modifier` takes a registered name
rather than a dotted path.

Then set `layout: "book"` on the block's config.

## Write it

Your template is the **body only**. Place controls with `{% control %}`:

```html
{% load plinta_form %}

<div class="row">
    <div class="col-4">{% control "title" %}</div>
    <div class="col-4">{% control "author" %}</div>
    <div class="col-4">{% control "published_on" %}</div>
</div>
<div class="row">
    <div class="col-6">{% control "region" %}</div>
    <div class="col-6">{% control "in_print" %}</div>
</div>
```

`{% control %}` draws the field's label, its control, its value, its choices,
the name the server reads and the box an error lands in.

## What you do not write

The mount, the JSON payload, the submit button and the error plumbing are the
component's. **This is deliberate, not an oversight.** A layout that owned them
could get one subtly wrong — a field name, a `data-kind`, the payload shape —
and the form would render perfectly and silently never save. The worst a layout
can do is leave a field out, which is visible.

So: no `<form>` tag, no submit button, and never name a field in an `input`
yourself.

## What to expect

**A control may be read-only, or draw nothing at all.** Which fields a form has
depends on the viewer. A column they may see but not change is *shown* — the
formatted value where the input would be — and one they may not see is not
drawn at all, with `{% control %}` rendering empty rather than failing. Write
the layout for the fullest case and let it thin out.

That is also all there is to "view mode": the same block and the same layout,
read by somebody holding `view` and not `change`.

**A field you never place is simply absent** from the form. That is a choice
your layout makes, so make it on purpose.

**An unregistered name stacks.** A block naming a layout nothing registered
still draws — the app that registered it may have been uninstalled — and
`plinta.components.W001` reports it at boot. Rendering will not.

## Verifying

```python
def test_it_places_the_fields(form_layout_registry):
    register_form_layout("book", "catalog/book_form.html")
    out = FormComponent().render(FormConfig(layout="book"), user, datasource=ds)
    assert 'name="title"' in out
    # and the shell is still the component's
    assert 'data-plinta-mount="form_plinta"' in out
```

Use the `form_layout_registry` fixture so a test's registration does not leak.

## Related

- `make-records-editable` — what has to be true before a form has any fields
- `add-settings-layout` — the same idea for a component's **settings**
- `add-component` — a widget that writes something a form does not

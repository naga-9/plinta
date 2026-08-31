---
name: add-filter-widget
description: Add a way of drawing a filter control — a searching multi-select, a slider, a colour picker, a tree chooser. Use when the filter bar should offer an input core does not draw. Not for changing what a control filters on; that is the control's own lookup.
---

# Add a filter widget

Core draws five — `input_plinta`, `boolean_plinta`, `select_plinta`,
`multiselect_plinta`, `daterange_plinta`. A sixth is registered, and a
`PageFilter` chooses it by name.

```python
# yourapp/apps.py
def ready(self):
    from plinta.pages.widgets import register_filter_widget

    register_filter_widget(
        "multiselect_tomselect",
        template="plinta/tomselect/multiselect.html",
        label="Multi-select (searching)",
        multiple=True,
        needs_options=True,
    )
```

```python
PageFilter.objects.create(
    page=page, field_name="store", label="Store",
    widget="multiselect_tomselect", lookup="in", data_source=source,
)
```

This is a registry rather than an enum on the model for the usual reason: a
closed set in core would mean a consumer who installs your widget has no way
to choose it.

## The two declarations that matter

**`multiple`** decides how the value is read. A repeated key —
`?store=1&store=2` — is read with `getlist`; `GET[name]` keeps only the
**last**, so a two-option selection would silently filter on whichever
happened to be last in the form. It also pairs with the `in` lookup.

**`needs_options`** decides whether `options_for()` is called. Leave it False
for anything the viewer types into: calling it would query for a list nothing
draws.

## Your template gets five names

```html
{{ control }}      the PageFilter — field_name, label, lookup
{{ value }}        the current value; a list when `multiple`
{{ options }}      [(value, label)], already scoped to the viewer
{{ truncated }}    True when the option list hit the cap
{{ control_id }}   the id the <label> points at — use it, or the label is dead
{{ cls }}          the style vocabulary: cls.select, cls.input, cls.help
```

Use `cls.*` rather than writing `pl-select`, so a style pack can rename your
control along with everything else.

## A multi-valued widget needs a hidden companion

```html
<input type="hidden" name="{{ control.field_name }}" value="">
<select multiple name="{{ control.field_name }}">…</select>
```

An unselected `<select multiple>` submits **nothing**, so the key vanishes from
the query string and the viewer's default is reapplied — they cannot express
"no filter". The hidden field keeps the key present; the empty value is
stripped, and the control arrives as an empty list.

## Options are the values that are there, and not yours to widen

`options_for` returns the **distinct values present in the rows the viewer can
see**, narrowed further by the other controls' selections. So a filter offers
what would match something: a viewer with no sales is offered no stores.

**Do not query the model yourself.** v1's equivalent did, took no user, and
listed every store by name to somebody who could see two stores' rows. The
scoping here comes with the rows rather than being added to them — a value
cannot appear unless a row carrying it is visible.

**`options` arrives already cascaded.** Your template renders what it is
given; deciding what to offer is not the widget's job.

If your widget fetches options as you type, the endpoint it calls has the same
obligation. A search that returns rows the viewer may not see is the same leak
arriving over XHR.

## Fetching, and why core has no size limit

Core's native `<select>` embeds every option, capped, and says when it capped.
That is why a widget that fetches is worth writing — and why core does **not**
refuse a large option set at save time: it would refuse a configuration that
becomes valid the moment somebody installs your widget.

## Rules

**Register from your own `AppConfig.ready()`.**

**Lowercase `[a-z][a-z0-9_]*`.** The name is stored on every `PageFilter` that
chooses it; renaming a widget orphans them.

**Name it `capability_implementation`** — `multiselect_tomselect`, not
`fancyselect`. The same convention components use, so a second vendor for the
same capability is obvious.

**One name, one widget.** A second registration raises rather than replacing.
To change how `select_plinta` draws, register your own and point the filters
at it.

**Degrade to a working control.** A widget whose JavaScript fails should leave
a usable native input behind, not an inert div — the bar is how a viewer
narrows a screen, and a dead control makes the page useless rather than plain.

## Verifying

```python
def test_two_values_survive(widget_registry):
    register_filter_widget("mine", template="x.html", multiple=True)
    request = RequestFactory().get("/", {"store": ["1", "2"]})
    assert submitted_filters(request, page) == {"store": ["1", "2"]}


def test_the_options_are_scoped(widget_registry):
    assert [label for _, label in options_for(control, mira)] == ["Hale Street"]
```

The second is the one worth writing. A widget that draws beautifully and
offers a row the viewer may not see has leaked, and nothing fails.

Use the `widget_registry` fixture so a test's registration does not leak.

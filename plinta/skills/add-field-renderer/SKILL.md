---
name: add-field-renderer
description: Draw one column as something other than text — a chip, a badge, a link, a progress bar, an avatar. Use when a cell needs markup or reads more of the row than its own value. Not for precision, a symbol or a unit; those are DataSourceField options.
---

# Add a field renderer

A field renderer draws one value as HTML, and **declares the relations it
reads**.

```python
# yourapp/renderers.py
from django.utils.html import format_html, format_html_join
from plinta.renderers.fields import register_field_renderer

@register_field_renderer("label_chips", prefetch_related=["labels"])
def label_chips(value, *, obj, field, user):
    return format_html_join(
        " ", '<span class="chip">{}</span>', ((label.name,) for label in obj.labels.all())
    )
```

Import that module from `AppConfig.ready()`, then point a column at it:

```python
DataSourceField.objects.create(
    data_source=books, field_name="title", label="Title", renderer="label_chips"
)
```

Binding is configuration, on the column — not a method on the consumer's model.
Plinta requires nothing of a consumer's models, and a renderer bound by a
`hasattr` check is that requirement under another name.

## Declare what you read

This is the reason it is a registration and not a function you call yourself.
Prefetch derivation reads **column paths**: a column named `title` implies no
joins. A renderer reaching `obj.labels` from that column is invisible to it, so
you get a query per row with nothing in the config to explain why.

```python
@register_field_renderer("owner_badge", select_related=["owner"])      # forward FK
@register_field_renderer("label_chips", prefetch_related=["labels"])   # m2m / reverse
```

`joins_for(columns)` collects them and they reach `get_queryset` as
`extra_select` and `extra_prefetch`. Declaring nothing is correct when you only
read `value`.

## The signature

`(value, *, obj, field, user)`, returning a string. It is called with keywords,
so accept `**kw` and take only what you use:

```python
def shout(value, **kw):
    return str(value).upper()
```

| | |
|---|---|
| `value` | the column's own value, already traversed |
| `obj` | the whole row — the reason a renderer can show more than one field |
| `field` | the `DataSourceField`, for `decimals`, `prefix`, a label |
| `user` | the viewer, when the cell varies by them |

## Output is trusted

A field renderer's return value is inserted **unescaped** — that is the point
of one. Registering a renderer is the same trust as writing a template, and the
same obligation:

```python
# wrong: a title containing <script> is now markup
return f"<span>{value}</span>"

# right
return format_html("<span>{}</span>", value)
```

Use `format_html`, `format_html_join`, or a rendered template. Never an f-string
around data.

## When you do not need one

**Precision, a symbol, a unit** are `DataSourceField` options — `decimals`,
`prefix`, `suffix`, `thousands_separator`. A renderer that only prepends `$` is
a column setting written the long way.

**A value the model does not store** is a computed column (`add-computed-column`),
which sorts and filters in the database. A field renderer cannot do either — it
runs in Python, after the rows are chosen.

Reach for a field renderer when the cell needs **markup**, or needs **more of
the row** than its own value.

## HTML only

Field renderers produce HTML. A spreadsheet, a CSV and an email call
`format_value` instead, because a chip is markup and a cell is not. So a column
with a chip renderer exports as its plain value, which is usually what an export
should contain anyway.

## Drawing with the shared classes

A renderer returns markup, so it names classes — and typed-in names stop
working for a project running a style pack (§10.9). Read them from the
vocabulary instead:

```python
from plinta.utils.styles import classes

def stock_badge(value, *, obj, field, user):
    cls = classes()
    return format_html(
        '<span class="{} {}">{}</span>',
        cls["chip"],
        cls["chip_success"] if obj.in_print else cls["chip_neutral"],
        "In print" if obj.in_print else "Out of print",
    )
```

**A status is the one place colour carries meaning** rather than decoration.
Two states drawn identically are a label nobody needs to scan; `chip_success`,
`chip_warning`, `chip_danger`, `chip_info` and `chip_neutral` exist for it.

**Only use a class the stylesheet defines.** A name nothing styles renders
plain and fails nothing — `pl-stat` shipped that way and drew a KPI figure at
body size.

## Rules

**One name, one meaning.** The registry is flat, so `status` must mean the same
thing on every model that uses it. Name it for what it draws — `state_badge`,
`owner_avatar`.

**Read only what you declared.** Reaching a relation you did not declare works,
and costs a query per row.

**Do not query.** No `.filter()`, no `.count()` inside a renderer: it runs once
per cell, so a single query there is a query per row per column.

## Verifying

A column naming a renderer nothing registered is a **boot error**
(`plinta.renderers.E001`), not an exception one row into the page.

The test worth writing is the join one, since that is the failure the
declaration exists to prevent:

```python
def test_it_costs_one_query(field_renderer_registry, django_assert_num_queries):
    select, prefetched = joins_for([column])
    rows = prefetch.apply(Book.objects.all(), ["title"],
                          extra_select=select, extra_prefetch=prefetched)
    with django_assert_num_queries(1):
        [render_field(b.title, column, obj=b) for b in rows]
```

Use the `field_renderer_registry` fixture so a test's registration does not leak.

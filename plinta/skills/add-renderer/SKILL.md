---
name: add-renderer
description: Add an output format — CSV, JSON, Markdown, an ICS feed. Use when the same rows and columns need to leave plinta as something other than a screen. Not for changing how one value looks; that is a field renderer.
---

# Add a renderer

A renderer turns rows and columns into one output format.

```python
# yourapp/renderers.py
import csv, io
from plinta.renderers.base import Renderer
from plinta.renderers.format import format_value
from plinta.renderers.registry import register_renderer

@register_renderer("csv")
class CsvRenderer(Renderer):
    content_type = "text/csv"
    extension = "csv"

    def render(self, rows, fields, config, user):
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow([f.label for f in fields])
        for row in rows:
            writer.writerow([format_value(value_of(row, f.field_name), f) for f in fields])
        return out.getvalue()
```

Import that module from `AppConfig.ready()`. The class is instantiated once at
registration, so a renderer holds no per-call state.

## A renderer never queries

This is the rule the whole layer rests on. `rows` arrives already filtered by
row policy, `fields` already filtered by field permission. A renderer that
issued its own query would bypass both, silently and with nothing to point at.

So: iterate `rows`, read attributes off them, and nothing else. No
`Model.objects`, no `.filter()`, no `get_object_or_404`, no `user.has_perm`.
Everything you are allowed to show is already in your hands.

```python
# wrong: a second query, unfiltered, that no permission check reaches
def render(self, rows, fields, config, user):
    return self.draw(Order.objects.all())

# right: what you were given
def render(self, rows, fields, config, user):
    return self.draw(rows)
```

## Use the shared formatters

`format_value(value, field)` honours `decimals`, `thousands_separator`,
`prefix` and `suffix` — which is what makes a date and a price look the same in
a table, a spreadsheet and an email. Reimplementing precision inside your
renderer is how a column ends up showing four decimals on screen and two in the
export.

`render_field` is the HTML path and returns markup. A CSV or a spreadsheet
wants `format_value`.

## Substitution

`get(format)` returns the HTML renderer when nothing registered `format`, so a
block defined against `xlsx` still renders on an installation without it. That
is why no package needs to import `contrib.export` to produce a file.

`require(format)` raises instead. Use it when a client asked for the format by
name — answering an `xlsx` request with an HTML page is worse than a 404.

## Rules

**Declare `content_type` and `extension`** if the output is served or offered
as a file. The defaults are an HTML page and no download.

**Return the format's natural type.** A string for text, `bytes` for a binary
format. Do not wrap it in an `HttpResponse` — the caller decides whether it is
a response, an email attachment, or a file on disk.

**Escape if your format needs escaping.** HTML does; CSV needs its own quoting,
which `csv.writer` handles. A format that concatenates strings without either
is a format that breaks on the first comma in a title.

**One name, one format.** `csv` is registered once. A second registration
raises rather than replacing, so two apps cannot silently fight over it.

## Verifying

```python
def test_it_never_queries(renderer_registry, django_assert_num_queries):
    rows = list(Order.objects.all()[:5])          # evaluated before the check
    with django_assert_num_queries(0):
        CsvRenderer().render(rows, fields, {}, user)
```

That test is worth writing for every renderer: it is the mechanical form of the
rule above, and it fails the moment someone reaches for the ORM.

Use the `renderer_registry` fixture so a test's registration does not leak into
the next one.

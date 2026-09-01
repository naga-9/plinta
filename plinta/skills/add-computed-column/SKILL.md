---
name: add-computed-column
description: Show a value the model does not store — a total, a latest reading, a bucket, a rank. Use when a column must sort and filter in the database, which a @property cannot. Not needed for a value that only needs displaying differently; that is a format.
---

# Add a computed column

A computed column is a registered ORM annotation. Name it in a `DataSourceField`
and it behaves like any other column: it sorts, it filters, it exports, and it
carries its own field permission.

```python
# yourapp/annotations.py
from django.db.models import DecimalField, F
from plinta.datasources.annotations import register_annotation

@register_annotation("order_total", output_field=DecimalField())
def order_total():
    return F("quantity") * F("unit_price")
```

Import that module from `AppConfig.ready()`, then create the column:

```python
DataSourceField.objects.create(
    data_source=orders, field_name="order_total", label="Total", sorter="number"
)
```

## Why not a `@property`

A property computes in Python, one row at a time, **after** the database has
already chosen and ordered the rows. So it cannot sort, cannot filter, cannot
paginate correctly, and costs a query per row if it touches a relation. An
annotation is part of the query. That is the whole distinction.

**A computed column is never editable.** It resolves to no model field, so
there is nothing to write to — `editable` on one mints a permission that can
never be honoured. It is also why `sorter` matters more here than elsewhere:
for a real column, what it *holds* is read from the model and `sorter` only
says how to compare it, but an annotation has no model field to read, so the
sort hint is all a filter or an alignment has to go on. Set it.

Use a property when the value is only ever read on one object you already have.

## Anything Django expresses

The boundary is where the expression is *authored*, not which expressions exist.

```python
@register_annotation("latest_price", output_field=DecimalField())
def latest_price():
    return Subquery(
        Price.objects.filter(book=OuterRef("pk")).order_by("-taken_at").values("amount")[:1]
    )

@register_annotation("is_overdue", output_field=BooleanField())
def is_overdue():
    return Exists(Task.objects.filter(book=OuterRef("pk"), due__lt=Now(), done=False))

@register_annotation("size_band")
def size_band():
    return Case(
        When(pages__lt=100, then=Value("short")),
        When(pages__lt=400, then=Value("medium")),
        default=Value("long"),
    )
```

## Declare `output_field`

A sorter and a filter widget are chosen from it **before any row exists**. Leave
it off only when Django can infer the type itself — `Upper("title")` is
obviously text; `F("a") * F("b")` across mixed types is not, and Django raises.

## It takes no arguments

Deliberately. An argument from configuration would be a path from stored data
into an ORM call, and therefore a validation surface — the kind that turns a
dashboard editor into a query author. You write the relation, you know the
model, you own the consequence.

Need two variants? Register two.

## Rules

**One name, one meaning, across every model.** The registry is flat, so
`order_total` must mean the same thing wherever it appears. A name that only
makes sense on one model should say so: `book_page_count`, not `count`.

**Lowercase `[a-z][a-z0-9_]*`.** It becomes a keyword argument to `annotate()`.

**An aggregate needs care.** `Count("book")` on a queryset that already joins
will over-count; add `distinct=True`, and check the number against the database
before trusting it.

**Do not shadow a model field.** Django refuses `annotate(title=…)` when `title`
is a field, and the error arrives at query time on the page that uses it.

## Verifying

Registration fails loudly at import; a *missing* registration is caught at boot
by `plinta.datasources.E001`, which lists what is registered. So a typo in a
`DataSourceField` is a startup error, not a blank column.

Test what a property could not do:

```python
def test_it_sorts_in_the_database(annotation_registry):
    rows = apply(Order.objects.all(), ["order_total"]).order_by("-order_total")
    assert [r.pk for r in rows] == [big.pk, small.pk]
```

Use the `annotation_registry` fixture so a test's registration does not leak
into the next one.

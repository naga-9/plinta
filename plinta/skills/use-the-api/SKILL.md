---
name: use-the-api
description: Read and write plinta data from a script, a partner system or another service. Use when something that is not a browser needs the data. Not for changing what a screen shows — that is a block, and its shape is not a contract.
---

# Use the data API

Install and mount it. The path is yours, because a library must not declare a
version whose path somebody else owns:

```python
INSTALLED_APPS = [..., "plinta.contrib.api"]

# yourproject/urls.py
path("api/v1/", include("plinta.contrib.api.urls")),
```

`/api/v1/docs` is the generated OpenAPI page.

## Publish a DataSource

Registering a model is not publishing it. Set **`show_in_api`** on the
DataSource — in the Data Sources screen or in a seeder:

```python
DataSource.objects.update_or_create(
    name="books",
    defaults={"content_type": ..., "label": "Books", "show_in_api": True},
)
```

That flag is **curation, not access control**. It decides what belongs in your
published surface; permissions decide who may read it. An unpublished
DataSource answers 404 rather than 403, because a caller has no business
learning that one exists and was not chosen for them.

## The seven endpoints

```
GET    /api/v1/data/                  the DataSources you may read
GET    /api/v1/data/{ds}/schema/      the fields you may see
GET    /api/v1/data/{ds}/             rows: filter, order, page, search
GET    /api/v1/data/{ds}/{pk}/
POST   /api/v1/data/{ds}/
PATCH  /api/v1/data/{ds}/{pk}/
DELETE /api/v1/data/{ds}/{pk}/
```

Seven in total — not seven per model. A `DataSourceField` already records the
path, label, type and filterability, which is a serializer definition, so
publishing a DataSource is the whole of adding a resource.

## Authenticate

```bash
curl -H "X-API-Key: plinta_…" https://example.com/api/v1/data/books/
```

Mint one against the user whose access the caller should have:

```python
from plinta.contrib.api.models import ApiKey

record, key = ApiKey.issue(name="nightly export", user=service_account)
print(key)   # the only time it exists in plaintext
```

**A key is a credential, not a permission system.** It resolves to a user and
every row policy, field permission and tenancy rule then applies unchanged. So
per-key field visibility needs no feature: mint the key against a service user
whose role lacks the field permission.

Only the hash is stored. If a key is lost, issue another and delete the old
one — nothing can recover it.

A browser session authenticates too, so exploring the docs signed in works
without a key.

## Query rows

```
GET /api/v1/data/books/?in_print=true&order=-published_on&page=2&size=100
GET /api/v1/data/books/?search=dune
```

Any parameter naming a visible, filterable column is a filter. `page`, `size`,
`order` and `search` are reserved. **The lookup comes from what the column
holds**, never from the query string — a boolean gets `exact`, text gets
`icontains` — so there is no `__regex` to send and no traversal to smuggle.

A parameter naming a column you cannot see is **ignored, not refused**.
Answering differently would tell you the column exists.

Responses are paginated with a hard cap on `size`. Permissions decide what you
may read; the cap decides how fast.

## Write

```bash
curl -X PATCH -H "X-API-Key: …" -H "Content-Type: application/json" \
     -d '{"title": "Dune"}' https://example.com/api/v1/data/books/7/
```

The body is `{column: value}`. Writes go through the **same pipeline the UI
uses**, so an API edit is authorised, validated, audited and notified exactly
like a screen edit — there is no second path to keep in step.

A field you may not write is **dropped**, and the response says what the row
now holds. A relation takes the pk; a many-to-many takes a list of them.

| Answer | Means |
|---|---|
| `401` | no credential, or a revoked one |
| `403` | you may not make this change |
| `404` | no such DataSource, or no such row *for you* |
| `422` | the model refused the values; `detail` says which field |

`404` rather than `403` for a row you cannot see is deliberate: a pk is a
number somebody can guess, and a 403 confirms the guess.

## Not this API

Wanting a table **exactly as it appears** — the block's columns, in order,
with a saved view applied — is a different question. Use the export path,
`/blocks/<name>/export/?format=json`.

`/api/v1/data/books/` is *the Book resource*; block-shaped output is *this
screen*. Unifying them would freeze the UI behind a version guarantee: editing
a block would be a breaking API change.

A saved **filter** is different again — it is values, not shape — so it
belongs here. Publish `FilterSet`, read its `values`, and pass them as
filters.

## Rules

**Never add a field-level API flag.** `view_{model}` and `view_{model}_{field}`
answer both questions already, and a second mechanism answering the same
question is one that drifts.

**Every entry point filters, not just the row fetch.** That is what makes the
absence of a flag safe: the listing is filtered by the model permission, the
schema by `get_available_fields`, the rows by `get_queryset`. Discovery must
not reveal what access denies.

**Breaking a published resource needs a new version**, not an edit.

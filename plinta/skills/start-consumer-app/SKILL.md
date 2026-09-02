---
name: start-consumer-app
description: Go from "I have Django models" to "I have screens" — register a DataSource, declare a policy, seed a page. Use when adding plinta to a project for the first time, or adding an existing app's models to it.
---

# Start a consumer app

Your models stay plain Django. Nothing inherits from plinta, nothing imports
it at module scope in `models.py`, and removing plinta leaves your models
untouched. Four steps, in this order — each depends on the one before.

## 1. Declare what you need, and register from `ready()`

```python
# yourapp/apps.py
from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = "catalog"

    #: Checked at boot. A missing layer is an error at startup, not a
    #: confusing failure on the first page load.
    requires = [
        "plinta.permissions",
        "plinta.datasources",
        "plinta.blocks",
        "plinta.pages",
        "plinta.shell",
    ]

    def ready(self):
        from catalog import plinta_registrations as registrations

        registrations.register_policies()
        registrations.connect_listeners()
```

**`ready()` is the only entry point plinta asks for.** Everything else —
policies, components, listeners, placeholders — is a call made from there.

Put the calls in their own module rather than in `ready()` itself. `ready()`
runs during app loading, so an import of your models at its top level is a
circular import waiting to happen.

## 2. Register a DataSource

A DataSource is the model plus the columns a screen may use. It is a database
row, not code, so it is created at `/data-sources/` (the screen plinta ships,
behind `view_datasource`), in the admin, or by a seeder. Write a seeder when
you want the registration reproducible across environments:

```python
source, _ = DataSource.objects.update_or_create(
    name="sales",
    defaults={"content_type": ContentType.objects.get_for_model(Sale),
              "label": "Sales"},
)
DataSourceField.objects.update_or_create(
    data_source=source, field_name="store__name",
    defaults={"label": "Store", "order": 10},
)
```

**Columns are not model fields.** A column exists because you listed it, and
saving one mints that column's permissions. Adding a model field does not add
a column, and you never add a model field to make something sortable.

Traversal with `__` works, and is the usual answer for anything on a related
model.

**Four `DataSourceField` options change how a column draws**, and all four read
from the declaration rather than from a value — a null in one row must not
align that cell differently from its column:

| Option | Effect |
|---|---|
| `visible` | in the **default column set**. A saved view may still name a column left out of it — the permission decides what may be *seen*, this decides what is shown unasked |
| `decimals` | right-aligned with tabular numerals |
| `format="textarea"` | wraps. Every other cell is `nowrap`, so long text would only scroll the table sideways |
| `width` | a fixed pixel width |

## 3. Declare a policy — before anyone sees a screen

**A model with no policy fails open.** Anyone holding `view_sale` sees every
sale, including other people's.

```python
# yourapp/plinta_registrations.py
from plinta.permissions.policies import PermissionPolicy, register_policy
from plinta.permissions.rules import FieldInUserSet, HasPerm, Owner, Public


def stores_of(user):
    return user.managed_stores.all()


class SalePolicy(PermissionPolicy):
    view = FieldInUserSet("store", user_set=stores_of)
    change = FieldInUserSet("store", user_set=stores_of)


register_policy(Sale, SalePolicy)
```

That is structural tenancy with no org package involved — core supplies the
shape, you supply what a store is and who manages one.

**Scope the children too.** A policy on `PurchaseOrder` says nothing about
`PurchaseOrderLine`, and the lines screen will leak. See `add-policy`.

The boot check `plinta.datasources.W001` names every DataSource-backed model
without a policy. Turn it into a test so the list only ever holds the ones you
meant.

## 4. Seed a page

```python
page, _ = Page.objects.update_or_create(
    slug="sales-overview",
    defaults={"title": "Sales", "menu_group": group, "order": 10},
)
PageBlock.objects.update_or_create(
    page=page, block=block,
    defaults={"row": 0, "column": 0, "width": 12, "height": 6},
)
```

It appears in the sidebar on its own, for whoever may open it. You do not
register a menu entry for a page.

## 5. Register your models in the admin

Optional, and worth it. plinta's own apps each ship an `admin.py` (§12.0), so
`DataSource`, `Block` and `Page` are editable there already; yours are not
until you say so.

```python
# yourapp/admin.py
@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "region")
    filter_horizontal = ("managers",)     # who manages what *is* your tenancy
```

**The admin knows nothing about policies.** It answers to `is_staff` and the
model permission, so it shows every row of everything to whoever may open it.
That is true of the admin for every Django app, and it is why the plinta
screens exist — use the admin to grant a permission and a plinta screen to see
what that did.

## Seeders are for demos and first runs, not for syncing

**Configuration lives in the database because people rearrange it in the
browser.** A seeder that runs against a live install clobbers their work.

Write it idempotent, match on natural keys, and run it to stand a project up —
then let the screens be edited where they are edited. If you need dev-to-prod
movement of configuration, that is an export, not a seeder that runs on deploy.

## Two tiers, always both

An action needs the Django model permission **and** the policy. The policy
narrows; it never grants. So a user who sees nothing usually needs the group
that grants tier 1, and `explain` will say so:

```python
from plinta.permissions import explain
print(explain(user, "view", sale))
```

That is the fastest answer to "why is this screen empty", and it is almost
always the first thing to run.

## What you do not do

**Do not import from a plinta module that is not in `add-*` skills.** Those
fourteen entry points are the surface that may not break without a deprecation
cycle. If your app needs a private path, that is a gap worth reporting rather
than a licence to reach inside.

**Do not add a base class to your models.** Not for workflow, not for audit,
not for comments. Every one of those attaches by registration.

**Do not write a superuser branch** in a policy. The engine handles it once.

## Verifying

```python
def test_a_manager_sees_only_their_stores(manager, other_store_sale):
    assert other_store_sale not in allowed(manager, "view", Sale.objects.all())

def test_policy_halves_agree(user):
    by_query = set(allowed(user, "view", Sale.objects.all()).values_list("pk", flat=True))
    by_check = {s.pk for s in Sale.objects.all() if can(user, "view", s)}
    assert by_query == by_check
```

The second is the one that catches real bugs: a policy whose queryset filter
and instance check disagree leaks on one screen and not the other.

## A worked example

`example/catalog` in the plinta repository is a complete consumer app —
models, policies, DataSources, blocks, pages, groups and a seeder — written
only against the published surface. Read it when a step here is too short.

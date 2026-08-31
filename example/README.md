# Marginalia Books — the plinta demo

A bookshop chain, built as an ordinary Django project that installs plinta.

**Nothing here is privileged.** Everything `catalog` does goes through the
published extension points, which is what makes this app the guard that the
API is real: if it ever needs a private path, that is a gap in the API.

## Running it

```
pip install -e ..
python manage.py migrate
python manage.py seed_catalog
python manage.py runserver
```

Django and pydantic, on Python 3.14 — `pip install -e ..` from here gets both.
`manage.py` puts the repository root on the path, so a clone runs the plinta
beside it rather than any other copy on the machine. A real consumer installs
the package and their `manage.py` is Django's own.

Sign in as `ada`, `mira`, `noor` or `sam` — password `demo`.

| who | role | sees |
|---|---|---|
| `ada` | Catalogue Administrator | everything |
| `mira` | Store Manager, Hale Street | Hale Street's sales and orders |
| `noor` | Store Manager, Marsh Lane | Marsh Lane's |
| `sam` | Catalogue Viewer | the catalogue, and no sales at all |

Sign in as `mira` and then `noor` and look at the Sales page. Same block, same
configuration, different rows — that is the policy engine scoping through the
consumer's own tenancy, with no organisation app installed.

## What it demonstrates

| door | where |
|---|---|
| a policy, scoped by the consumer's own tenancy | `SalePolicy` |
| a row-owned, shareable model | `PromotionPolicy` |
| a model with **no** policy, deliberately | `Book` |
| a computed column that sorts in the database | `sale_total` |
| a queryset modifier | `open_orders` |
| a placeholder resolved per viewer | `__MY_STORES__` |
| field renderers, one declaring its joins | `stock_badge`, `store_link` |
| a registered action | `export` |
| **a component, from outside core** | `stat` |
| an event listener replacing a pipeline stage | `record_stock_movement` |
| a capability probing a generic relation | `catalog_notes` |
| a screen that is not a Page | `catalogue_admin` |

All in `catalog/plinta_registrations.py`, in one sitting's worth of reading.

## Two axes of permission

`setup_groups` creates four roles, and the split is the point:

- **Store Manager** is about the *data* — it grants `change_sale`, and
  `SalePolicy` narrows that to the manager's own stores.
- **Catalogue Author** is about the *screens* — it grants `add_page` and
  `change_block`, and no sales at all.

They are orthogonal. A shopkeeper has no business rearranging dashboards, and
a dashboard editor has no business reading the chain's takings.

**Run `setup_groups` after the screens are configured.** Column permissions are
minted when a `DataSourceField` is saved, so a role built beforehand grants
`view_sale` and none of its columns, and every table renders empty.
`seed_catalog` calls it in the right order for you.

## What `manage.py check` says

One warning, and it is deliberate:

```
plinta.datasources.W001: books shows Book rows with no registered policy
```

The catalogue is shared — every holder of `view_book` sees all of it. A second
name in that list would be a leak, and a test asserts there is only ever one.

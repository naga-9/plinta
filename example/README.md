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

### Updating an existing copy

`seed_catalog` is idempotent, so pulling and re-running it is the whole update
— it re-seeds the data, registers plinta's shareables and rebuilds the roles
in the right order:

```
git pull
pip install -e ..
python manage.py migrate
python manage.py seed_catalog --no-users   # keeps your logins and passwords
python manage.py runserver
```

**Re-running it is not optional after a pull.** Permissions are minted when a
`DataSourceField` is saved, so a role built before a new column exists grants
nothing for it — and new controls appear only for people who hold the new
permission. If a button you expected is missing, this is the first thing to
check and the second is which user you signed in as.

**Restart the server.** `--noreload` is convenient and will happily serve the
code you had before the pull.

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

The roles differ in what they may *do*, not only what they may see — the
saved-view controls on a card are the clearest case:

| | `sam` | `mira` | `ada` |
|---|---|---|---|
| **Views** button on a card | — | yes | yes |
| save a view for themselves | — | yes | yes |
| publish one to everyone | — | — | yes |
| **Add** button on the books card | — | — | yes |

So a card looks different depending on who is looking, and an empty header on
`sam`'s screen is the permissions working rather than a missing feature. The
last row is the one worth reading twice: `mira` may add a **sale** and not a
**book**, so the Add button follows the block's own model rather than the
person's seniority.

A fifth login, `root`, is a Django superuser for `/admin/`, where users and
groups are edited. **Do not browse the demo as `root`:** a superuser is the
permission engine's one bypass, so both tiers stop applying and every store's
rows appear at once — which is precisely what `mira` and `noor` are here to
disprove. Django's admin is not how plinta screens are meant to be used; it is
installed so there is somewhere to grant a permission and watch a screen
change.

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

## Columns are granted, not implied

Every role names its column permissions one at a time. `view_sale` says a
person may see sales; `view_sale_sale_total` says they may see what one came
to. Deriving the second from the first would mean anybody who can open a
screen can read every column on it, which is what field permissions exist to
prevent — so the lists are long on purpose.

The sharpest case is plinta's own:

| | Store Manager | Catalogue Author |
|---|---|---|
| save a view for themselves | yes | yes |
| rename it | yes | yes |
| **publish it to everyone** | **no** | yes |

Publishing sets `SavedView.owner` to null, so it is a change to one field and
`change_savedview_owner` is what gates it. That permission exists only because
`seed_shareables` registers `SavedView` as a DataSource — a field permission
comes from a `DataSourceField` row and from nothing else.

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

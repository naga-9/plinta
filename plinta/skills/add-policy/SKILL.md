---
name: add-policy
description: Control which rows of a model a user may see or change. Use when row-level access matters — an owner's own records, a region's stores, anything shared. Not needed when the Django model permission alone is the right answer.
---

# Add a policy

A policy says which **rows** of one model an action applies to. It composes
rules, and is registered against the model rather than attached to it, so your
models stay plain Django.

```python
# yourapp/policies.py
from plinta.permissions import PermissionPolicy, register_policy
from plinta.permissions.rules import InstancePerm, Owner, Public

class BookPolicy(PermissionPolicy):
    view   = Owner() | Public() | InstancePerm("catalog", "book", "view")
    change = Owner() | InstancePerm("catalog", "book", "change")
    delete = Owner()

register_policy(Book, BookPolicy)
```

Import that module from `AppConfig.ready()`.

## When you do not need one

**The model permission alone may be the right answer.** With no policy, anyone
holding `view_book` sees every book — correct for a shared catalogue, wrong for
personal dashboards. Row control is opt-in, and most models never need it.

Be deliberate: a missing policy **fails open**, which is why a boot check lists
every DataSource-backed model without one.

## Scoping a parent does not scope its children

A policy governs **one model**. Writing one for `PurchaseOrder` says nothing
about `PurchaseOrderLine`, so the lines stay visible to anyone holding
`view_purchaseorderline` — including lines of orders they may not see.

This hides well, because the parent screen is correct and only the child screen
leaks. Give the related model its own policy, usually the same rule through the
relation:

```python
class PurchaseOrderPolicy(PermissionPolicy):
    view = FieldInUserSet("store", user_set=stores_of)

class PurchaseOrderLinePolicy(PermissionPolicy):
    view = FieldInUserSet("order__store", user_set=stores_of)   # through the parent
```

Nothing infers this, deliberately: a relation is not evidence of a scope. A
`Sale` points at a `Book`, and scoping books by whoever sold one would be
absurd. Only you know whether the child inherits the parent's rule.

**The boot check is what tells you.** `plinta.datasources.W001` names every
DataSource-backed model without a policy. Turn it into a test, so the list can
only ever contain the models you meant:

```python
def test_the_only_unscoped_model_is_the_one_we_meant():
    reported = {w.obj.name for w in check_datasource_models_have_a_policy()}
    assert reported == {"books"}          # the shared catalogue, deliberately
```

## Two tiers, always both

An action needs the Django model permission **and** the policy. The policy
narrows; it never grants. A user with no `view_book` sees nothing however
generous the policy is — which is what stops sharing from escalating access:
a share grants tier 2, and the recipient still needs the role that grants tier 1.

## Silence is not denial

An action your policy does not declare is decided by the model permission
alone. `BookPolicy` above says nothing about `export`, so `export_book` governs
it entirely.

It does **not** inherit `view`. If an action should be as narrow as viewing,
declare it:

```python
class BookPolicy(PermissionPolicy):
    view = Owner() | Public()
    export = view          # same rule, stated rather than assumed
```

## A scope provider is a policy

Structural scoping — "this user's region", "this user's desk" — is not a
separate mechanism. Bind `FieldInUserSet` to your own tenancy:

```python
class BookPolicy(PermissionPolicy):
    view = FieldInUserSet("region", user_set=lambda u: u.regions.all())
```

The engine never imports a provider. `contrib.organization` is one, not the one.

## Rules

**Never write a superuser branch.** The engine handles it, in one place. A
policy that tried would only matter when someone forgot it — and then it locks
superusers out of that model.

**Never check `is_staff`.** That flag means "may log into `/admin/`" and nothing
else. Use `HasPerm("app.some_permission")` for a capability.

**`Public` says nothing about the user** — it admits a row with **no owner**. It
never stands alone for editing, or anyone at all may edit public rows. Pair it:
`Public() & HasPerm("catalog.change_book_owner")`.

**Keep it declarative.** A rule composes with `|`, `&` and `~`. If you reach for
`Callable`, check first whether two existing rules combine — it exists as an
escape hatch and every use is a small gap in the vocabulary.

## Verifying

```python
from plinta.permissions import allowed, can, explain

allowed(user, "view", Book.objects.all())     # the rows
can(user, "change", book)                     # this row
print(explain(user, "change", book))          # why not
```

`explain` prints the tier that failed and which branch of the tree refused —
the fastest answer to "why can't this user see this row".

**Test the invariant, not an expected list.** Filtering with `allowed` and
checking each row with `can` must select the same set; a policy whose two halves
disagree is the failure the rule pairing exists to prevent.

```python
def test_policy_halves_agree(user):
    by_query = set(allowed(user, "view", Book.objects.all()).values_list("pk", flat=True))
    by_check = {b.pk for b in Book.objects.all() if can(user, "view", b)}
    assert by_query == by_check
```

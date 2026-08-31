---
name: add-rule
description: Add a new condition to the permission vocabulary, as a Q and a predicate from one declaration. Use only when no combination of the eleven existing rules expresses the condition — most needs are a composition, not a new rule.
---

# Add a rule

A rule is one condition, declared twice over: as a `Q` that filters a queryset,
and as a predicate that tests a single instance.

```python
from django.db.models import Q
from plinta.permissions.rules import Rule

class SameRegionAs(Rule):
    """The row is in a region the user works in."""

    def __init__(self, field="region"):
        self.field = field

    def to_q(self, user):
        if not user.is_authenticated:
            return DENY
        return Q(**{f"{self.field}__in": user.regions.all()})

    def evaluate(self, user, instance):
        if not user.is_authenticated:
            return False
        return getattr(instance, f"{self.field}_id") in {r.pk for r in user.regions.all()}
```

## First: check it is not a composition

Eleven rules ship, and most conditions are a combination of them.

| You want | Already exists |
|---|---|
| the user's own rows | `Owner()` |
| rows with no owner | `Public()` |
| a per-row grant | `InstancePerm(app, model, action)` |
| a capability the user holds | `HasPerm(codename)` |
| a field equals a literal | `FieldEq(field, value)` |
| the row's FK is in a set derived from the user | `FieldInUserSet(field, user_set)` |
| the user is in a user-M2M | `UserInM2M(field)` |
| the user's group is in a group-M2M | `GroupOverlap(field)` |
| a permission on the row's generic parent | `ParentModelPerm(action)` |

`SameRegionAs` above is a worked example, not advice — it is
`FieldInUserSet("region", lambda u: u.regions.all())` and should not be written.

A new rule is justified when the condition is genuinely absent from that list
**and** appears in more than one policy. One policy with an odd condition wants
`Callable`, not a new rule.

## The invariant

**`to_q` and `evaluate` must select the same rows.** A row surviving the filter
must pass the check, and a row failing the filter must fail it.

Break this and the failure is silent and asymmetric: a table lists a row the
edit form then refuses, or a row is editable but invisible. Nothing raises.

The pairing exists so both come from one declaration. Do not implement them
from separate reasoning.

## Rules

**Guard anonymous in both halves.** `Q(owner=AnonymousUser())` fails at query
time — an anonymous user has no primary key. Return `DENY` and `False`. The
engine denies anonymous first, so this is belt and braces, but a rule is public
API and may be called directly.

**`to_q` returns `DENY` or `ALLOW`, never a bare `Q()`.** Both are importable
from `plinta.permissions.rules`:

```python
DENY  = Q(pk__in=[])        # matches nothing
ALLOW = Q(pk__isnull=False) # matches every row
```

Getting denial the wrong way round turns it into a full grant — `Q()` is the
*empty* filter and matches everything. But "allow everything" needs the
explicit form too, and for a subtler reason: **`Q()` is falsy and Django's
combination short-circuits.**

```python
>>> Q() | Q(store__in=[3])
<Q: (AND: ('store__in', [3]))>     # the branch admitting everything vanished
```

So `HasPerm(...) | FieldInUserSet(...)` would list fewer rows than `can()`
admits one at a time — the two halves of a policy disagreeing, which is the
invariant `add-policy` asks every policy to hold. `HasPerm` returned `Q()` and
did exactly this until it was found by a demo where head office saw no rows
while `explain()` said ALLOWED.

**Read the id, not the object.** In `evaluate`, `instance.region_id` is already
in memory; `instance.region` is a query per row. And never as a `getattr`
default — `getattr(x, "region_id", getattr(x, "region", None))` evaluates the
default eagerly and loads the object anyway.

**Take the field name as an argument.** `Owner(field="created_by")` serves a
model that names its owner differently. A rule hardcoding a column serves one
model.

**Do not raise on a missing attribute.** A policy may be applied to a model
lacking the field; return False rather than exploding mid-queryset.

## Verifying

Test the invariant against a real table, not an expected list:

```python
def assert_halves_agree(rule, user, model):
    by_query     = set(model.objects.filter(rule.to_q(user)).values_list("pk", flat=True))
    by_predicate = {row.pk for row in model.objects.all() if rule.evaluate(user, row)}
    assert by_query == by_predicate, f"{rule!r} disagrees with itself"
```

Run it with rows that match, rows that do not, an empty table, and an anonymous
user. An assertion on a literal set would pass even after the two halves drifted
apart; this cannot.

Add a `label` if the default `repr` reads badly in a decision trace — `explain`
prints it, and a rule nobody can read in a trace is a rule nobody can debug.

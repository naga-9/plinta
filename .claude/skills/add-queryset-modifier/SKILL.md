---
name: add-queryset-modifier
description: Narrow what a block shows beyond its DataSource — open items only, this quarter, my team's rows. Use when a screen needs a filter that configuration cannot express. Not for access control; that is a policy.
---

# Add a queryset modifier

A modifier is a named callable that narrows a queryset. A block stores the
**name**; the registry resolves it.

```python
# yourapp/modifiers.py
from plinta.datasources.modifiers import register_queryset_modifier

@register_queryset_modifier("open_orders")
def open_orders(queryset, user, **kwargs):
    return queryset.exclude(status="closed")
```

Import that module from `AppConfig.ready()`.

## Why a name and not a path

A dotted path in configuration is a path from stored data into `import_module`.
Anyone who can edit a block could then name any importable callable in the
process. The registry closes that: a stored value can only reach code someone
deliberately registered.

## It may narrow; it must not widen

Everything above this layer assumes what it receives is already
permission-filtered. A modifier that adds rows defeats that **silently** — no
error, no trace, just rows on a screen that should not show them.

So: `.filter()`, `.exclude()`, `.distinct()` — never `|`, never a fresh
`Model.objects.all()`, never `union()`.

```python
# wrong: starts over, and loses the filtering it was handed
def mine(queryset, user, **kwargs):
    return Order.objects.filter(owner=user)

# right: narrows what it was given
def mine(queryset, user, **kwargs):
    return queryset.filter(owner=user)
```

## Not a substitute for a policy

| | policy | modifier |
|---|---|---|
| decides | what a user **may** see | what this screen **chooses** to show |
| applies to | every read of the model | one block |
| bypassable | no | yes — another block simply omits it |

A modifier is presentation. If removing it would expose rows a user must not
see, it was doing a policy's job — move it. See `add-policy`.

## Signature

`(queryset, user, **kwargs)`, returning a queryset.

`user` is always passed, so a modifier may be user-relative without a second
mechanism. Accept `**kwargs` even when you ignore it — a caller passing a
parameter you did not expect should not be a `TypeError` on a live page.

```python
@register_queryset_modifier("recent")
def recent(queryset, user, *, days=30, **kwargs):
    return queryset.filter(created_at__gte=timezone.now() - timedelta(days=days))
```

## Rules

**Return a queryset, not a list.** Slicing or `list()` here breaks pagination,
ordering and counting for every caller above.

**Do not evaluate it.** No `len()`, no `if queryset:` — that runs the query, and
then runs it again when the page renders.

**One name, one meaning.** The registry is flat. `open` is too vague to be
registered once; `open_orders` is not.

**Keep it cheap.** It runs on every render of every block that names it, and
composes with whatever the page filter bar has already applied.

## Verifying

```python
from plinta.datasources.modifiers import apply_modifier

def test_it_only_narrows(modifier_registry, user):
    base = Order.objects.all()
    assert set(apply_modifier("open_orders", base, user)) <= set(base)
```

That subset assertion is the one test worth writing for every modifier — it is
the invariant the whole layer above depends on.

Naming an unregistered modifier raises `ModifierError` listing what *is*
registered, rather than rendering every row it was meant to hide.

Use the `modifier_registry` fixture so a test's registration does not leak.

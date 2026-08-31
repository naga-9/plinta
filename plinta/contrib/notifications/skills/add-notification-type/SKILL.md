---
name: add-notification-type
description: Say that something is worth telling somebody about — a sale recorded, an order approved, a comment on your record. Use when an event should reach people. Requires plinta.contrib.notifications.
---

# Add a notification type

**Requires `plinta.contrib.notifications` in `INSTALLED_APPS`.**

A subscription says which model, which event, who hears, and under what
condition:

```python
# yourapp/notifications.py
from plinta.contrib.notifications.registry import register_notification

register_notification(
    "large_sale",
    "catalog.Sale",
    "created",
    recipients=lambda obj, **kw: obj.store.managers.all(),
    when=lambda obj, **kw: obj.total > 1000,
    title=lambda obj, **kw: f"A large sale at {obj.store}",
    body=lambda obj, **kw: f"{obj.book} for {obj.total}",
    url=lambda obj, **kw: obj.get_absolute_url(),
    channels={"email": True},
)
```

Import that module from `AppConfig.ready()`.

## It is code, not a table

There is no screen for editing these, deliberately. A table of rules would make
"who gets told" a validation surface and a place for a stored callable path —
and a stored `{obj.owner.email}` template is configuration turned into
attribute traversal.

A registration is code, reviewed like code.

## The events you may name

`written`, `created`, `updated`, `deleted`, `state_changed`, `comment_posted`.
Each maps to a core signal; nothing here invents one, and naming something else
raises at import.

`created` and `updated` are the two halves of `written` — use them when the
distinction matters, which for a notification it usually does.

## `when` is where the noise is controlled

**Without it, every occurrence notifies.** A subscription on `updated` for a
model people edit all day is how a product teaches its users to ignore the
bell.

Filter to what is worth interrupting somebody for. If you cannot write the
condition, the answer is usually that this belongs in a digest or an audit
trail rather than a notification.

## `recipients` returns users, not roles

It takes the object and the event's payload and returns an iterable of users.
Resolve the role yourself:

```python
recipients=lambda obj, **kw: User.objects.filter(groups__name="Buyers")
```

**Return a queryset, not a list comprehension over everybody.** This runs
inside the write.

**It is not permission-checked.** Naming a recipient sends them the title and
body you wrote, so do not put in them anything the recipient may not see.

## The actor does not hear by default

`notify_actor=False` is the default, and right nearly always: the person who
just saved the thing knows they saved it. Set it True only for something
genuinely worth confirming back — an action that succeeded asynchronously.

## `channels` overrides the defaults for this kind

`{"email": True}` mails about this even when email is off by default. Reserve
it for things that justify arriving in somebody's inbox; a user's own
preference still wins where they have expressed one.

## Rules

**Lowercase `[a-z][a-z0-9_]*`, one name per project.** The name is a
preferences key — users can turn a kind off — so renaming one orphans their
setting.

**`title`, `body` and `url` are a string or a callable, never a format
template.**

**Keep the callables cheap and total.** They run inside the write. A `title`
that raises on an edge case fails the save that caused it.

**Model label is `"app_label.ModelName"`**, matched case-insensitively. It is
a string rather than an import so this module does not depend on the app it
notifies about.

## Verifying

```python
def test_only_large_sales_notify(subscription_registry):
    register_notification("large_sale", "catalog.Sale", "created",
                          recipients=lambda obj, **kw: [manager],
                          when=lambda obj, **kw: obj.total > 1000)
    Sale.objects.create(store=store, total=10)
    assert not Notification.objects.exists()
    Sale.objects.create(store=store, total=5000)
    assert Notification.objects.count() == 1
```

Test the `when`, not the registration. The condition is the part that is
actually load-bearing, and the part that goes wrong.

Use the `subscription_registry` fixture so a test's registration does not leak.

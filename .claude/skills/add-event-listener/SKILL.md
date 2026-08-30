---
name: add-event-listener
description: React to a write, delete, state transition or comment anywhere in plinta, without importing whatever caused it. Use when a package should do something in response to another package's activity — audit a change, send a notification, sync a derived row.
---

# Add an event listener

Five signals carry everything plinta mediates. A listener imports the signal
from `plinta.events` and never from whatever emitted it, so two packages can
observe each other with no dependency between them.

| Signal | Fires | Adds to the envelope |
|---|---|---|
| `object_writing` | before a write is saved | `mode`, `fields` |
| `object_written` | after the save and its M2M | `mode`, `changes` |
| `object_deleted` | after a row is deleted | `pk` |
| `state_changed` | a state machine moved a row | `from_state`, `to_state`, `comment`, `metadata` |
| `comment_posted` | a comment was posted | `body`, `metadata` |

Every one carries the same envelope: **`obj`, `actor`, `source`**. Subscribe to
several and read one shape.

## Steps

1. Put handlers in `listeners.py` in your app.

```python
from django.dispatch import receiver
from plinta.events import object_written

@receiver(object_written)
def record_change(sender, obj, mode, changes, actor, source, **kwargs):
    for field, (before, after) in changes.items():
        AuditLog.objects.create(
            content_object=obj, field=field, old=before, new=after,
            actor=actor, source=source,
        )
```

2. Import the module from `AppConfig.ready()` so the handlers connect at startup.

```python
class AuditConfig(AppConfig):
    def ready(self):
        from . import listeners  # noqa: F401
```

3. Nothing else. No registration, no declaration — a listener creates no
   dependency on whoever emits.

## Filter at connection time, not inside the handler

The sender is the **model class**:

```python
@receiver(object_written, sender=PurchaseOrder)
def on_order_written(sender, obj, changes, **kwargs):
    ...
```

Better than `if isinstance(obj, PurchaseOrder)` inside a handler that Django
called for every write in the system.

## Rules

**Always take `**kwargs`.** A signal may gain a payload key; a handler with a
fixed signature breaks when it does.

**Do not raise.** An exception is logged and swallowed, so raising loses the
work silently rather than surfacing it — and it never reaches the user, because
a failing listener must not fail someone's save. Handle your own errors.

**Do not depend on ordering.** Listener order is undefined. Two handlers that
must run in sequence are one handler.

**Be fast.** Handlers run inside the write's transaction. Anything slow — email,
an HTTP call, a report — belongs in a queue you own.

**Wrap in `transaction.on_commit` if you need the write to be durable.**
Signals fire *inside* the transaction, so audit gets atomicity. A listener that
must not act on a write that later rolls back opts in:

```python
@receiver(object_written)
def notify(sender, obj, actor, **kwargs):
    transaction.on_commit(lambda: send_email(obj, actor))
```

**`object_deleted` carries `pk` separately.** Django clears the primary key on
the instance, so `obj.pk` is None by the time you see it. Use `kwargs["pk"]`.

## Coalescing in a batch

An import of 5,000 rows emits 5,000 signals. To act once instead:

```python
from plinta.events import current_batch

@receiver(object_written)
def record_change(sender, obj, changes, **kwargs):
    batch = current_batch()
    if batch is None:
        write_row(obj, changes)                      # no batch: act now
        return
    if not buffer:
        batch.on_exit(lambda: bulk_write(buffer))    # register once
    buffer.append((obj, changes))
```

Flushes run when the outermost batch exits, **including when the body raised** —
so buffered rows are released either way rather than leaking into the next batch.

A listener that ignores batches still behaves correctly, just slower.

## Verifying

```python
from plinta.events import emit_written, has_listeners
has_listeners(object_written)          # is anything connected at all?
emit_written(book, mode="update", changes={"price": (9.99, 12.5)}, source="test")
```

A handler that raises will not fail this call — check the log for
`object_written listener <module>.<name> failed`.

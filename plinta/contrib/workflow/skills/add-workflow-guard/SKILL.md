---
name: add-workflow-guard
description: Add a condition a transition must satisfy beyond a permission — "this order has no open lines", "this invoice is fully paid". Use when whether a move makes sense depends on the row. Requires plinta.contrib.workflow.
---

# Add a workflow guard

**Requires `plinta.contrib.workflow` in `INSTALLED_APPS`.**

Every move passes three gates, and they answer different questions:

| Gate | About | Refuses when |
|---|---|---|
| the transition's **permission** | the person | they do not hold it |
| the **row policy** | their reach | the row is not theirs to change |
| the **guard** | the row itself | "this order still has open lines" |

They are separate because no grant can express a condition about a row, and no
condition should decide who is allowed.

```python
# yourapp/apps.py
def ready(self):
    from plinta.contrib.workflow.guards import register_guard

    register_guard(
        "no_open_lines",
        "no open lines",
        check=lambda obj, **kw: (
            not obj.lines.filter(open=True).exists()
            or "This order still has open lines."
        ),
    )
```

Then name it on the transition row. A guard is registered **by name**, never
resolved from a stored dotted path, so a transition cannot name arbitrary
importable code.

## Return a reason, not just False

`True` permits. `False` refuses with a generic message. A **string** refuses
with that string, and the string is what the screen shows.

Write the string. `available()` returns refused moves along with why, so a
button can be greyed out with "This order still has open lines" — a move that
simply vanishes reads as a missing feature, and one that fails silently reads
as a bug.

## Raising refuses

A guard that raises is logged and refuses, with the exception in the reason.
Permitting on error would wave through exactly the move the condition was
written to stop.

So a guard that queries a service which is down blocks the workflow. If that is
wrong for your case — if the move should proceed when the check cannot be made
— catch it yourself and return True deliberately.

## It runs on every render, not just on the move

`available()` calls every candidate transition's guard to decide what to draw.
A guard doing a slow query costs that on each detail page, once per transition
out of the current state.

Count with `exists()`. If the answer needs real work, denormalise it onto the
row and guard on the column.

## Not a policy, and not a permission

**Not a policy:** a policy narrows which rows a user may reach at all, and it
filters querysets. A guard answers whether a move makes sense on a row they can
already reach — it never filters anything.

**Not a permission:** if the condition is about the person, it is the
transition's permission, which is minted for you and grantable on its own.

If your guard reads `user` to decide, look again — that is nearly always one of
the other two gates in the wrong place.

## Rules

**Register from your own `AppConfig.ready()`**, before any transition names it.

**Lowercase `[a-z][a-z0-9_]*`.** Transition rows store the name; renaming a
guard orphans every transition pointing at it.

**One name, one guard.** A second registration raises rather than replacing.

**A name nothing registered raises when evaluated**, listing what is registered.
A transition naming a missing guard must not simply proceed — the condition was
written down because somebody meant it to hold.

**Keep it side-effect free.** It runs on render, repeatedly, for moves nobody
takes.

## Verifying

```python
def test_the_reason_reaches_the_screen(guard_registry):
    register_guard("no_open_lines",
                   check=lambda obj, **kw: "This order still has open lines.")
    move = next(m for m in available(order, user) if m.transition == close)
    assert not move.permitted
    assert move.reason == "This order still has open lines."


def test_a_raising_guard_refuses(guard_registry):
    register_guard("boom", check=raises)
    with pytest.raises(TransitionDenied):
        execute(order, close, user)
```

The second is the one worth writing, because failing open here is silent and
the failure is a row in a state it should never have reached.

Use the `guard_registry` fixture so a test's registration does not leak.

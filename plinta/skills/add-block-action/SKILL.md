---
name: add-block-action
description: Put a control in a block card's header — an export menu, a "new record" button, a column chooser, a link to the block's settings. Use when an app adds something you do *to* a block. Not for a control on every screen; that is a topbar item.
---

# Add a block action

The right-hand side of a card's header. Core registers one — the saved-view
picker — and everything else is registered by whoever provides it.

```python
# yourapp/apps.py
def ready(self):
    from plinta.blocks.actions import register_block_action

    register_block_action(
        "export",
        template="plinta/export/button.html",
        permission="plinta_blocks.export_block",
        components={"table_plinta", "table_tabulator"},
        order=20,
    )
```

Core's card names no package that might not be installed, which is the whole
reason this is a registry: an export button built into the header would draw
for an installation without `contrib.export` and point at nothing.

## Say which components it suits

```python
components={"table_plinta"}      # this one only
components=None                  # anything
```

A column chooser belongs to a table. An export belongs to anything with rows.
A "new record" button belongs to anything reading a model a viewer may add to.
**An action offered on a component that cannot honour it is a button that does
nothing**, which is worse than an absent one — it looks like a feature that
broke.

## `when` reads; it does not look up

```python
when=lambda views=(), **kw: bool(views)
```

The card passes what it already knows — the block's saved views, say. **Take
it from the arguments and never query.** One query per block per action is how
a dashboard of eight blocks becomes forty round trips, and the page's
query-count test will fail before you notice.

Accept `**kwargs`. The card may pass more later, and a callable that named
only what it needed would break when it does.

**A `when` that raises hides its own action** and nothing else. A card must not
go down because one control could not decide whether to draw.

## Your template gets the slot

```html
{{ slot.placement }}   the PageBlock — its pk, its title, its position
{{ slot.views }}       the block's saved views, already permission-filtered
{{ slot.view }}        the one in force
{{ slot.param }}       this placement's query-string prefix, "b3_"
{{ slot.form_url }}    where this card opens a record's form
{{ cls }}              the style vocabulary
```

**To open a record's form, carry the URL and nothing else:**

```html
<button type="button" data-plinta-open-form="{{ slot.form_url }}">Add</button>
```

Core's dialog is listening for that attribute anywhere on the page, so your
action never learns what a modal is. No `?record=` is a create; core's
`add_record` action is exactly this and nothing more.

**Use `data-plinta-open-form`, never the attribute a mount carries for the
same URL.** The listener matches with `closest`, which walks *upwards*: share
a name with the mount and every click inside the card opens a form, including
the clicks meant for the widget.

**Prefix every parameter you own with `slot.param`.** Two of the same block on
one page must act independently — it is why sorting, paging and the view
picker all carry it. A bare `?view=2` would move both.

## Three gates, in order

| Gate | Refuses |
|---|---|
| `components` | a component that cannot honour the action |
| `permission` | a viewer who may not do it |
| `when` | this block, now — a condition a permission cannot express |

Use the cheapest that fits. A permission is a grant somebody can be given;
`when` is a fact about the block. "May export" is a permission; "has anything
to export" is a `when`.

## Rules

**Register from your own `AppConfig.ready()`.**

**Lowercase `[a-z][a-z0-9_]*`.** The name is not stored in configuration, but
it is the registry key and a second registration under it raises.

**`order` places it.** Core's view picker is 10. Leave room.

**Draw nothing rather than something disabled.** A card header is small, and a
greyed control that never becomes usable is worse than a gap — unlike a
workflow transition, where the reason a move is refused is the useful part.

## Verifying

```python
def test_it_is_offered_only_where_it_fits(block_action_registry):
    register_block_action("columns", template="x.html", components={"table_plinta"})
    assert actions_for(table_block, ada)
    assert actions_for(chart_block, ada) == []


def test_its_condition_costs_no_query(block_action_registry, django_assert_num_queries):
    register_block_action("picker", template="x.html", when=lambda views=(), **kw: bool(views))
    with django_assert_num_queries(0):
        actions_for(block, ada, views=[])
```

The second is the one worth writing. An action whose condition queries works
perfectly and makes every page slower in proportion to how many blocks it has.

Use the `block_action_registry` fixture so a test's registration does not leak.

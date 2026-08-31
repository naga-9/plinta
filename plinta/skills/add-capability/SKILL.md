---
name: add-capability
description: Attach a section to every record that has one — comments, attachments, a checklist, an audit trail. Use when your app adds something to other people's models. Not for a widget on a dashboard; that is a component.
---

# Add a capability

A capability puts your app's section on a record's edit form, and your app's row
in the capability matrix. Both aspects are registered together, from your own
app.

```python
# yourapp/capabilities.py
from django.apps import apps
from django.contrib.contenttypes.fields import GenericRelation

from plinta.blocks.capabilities import register_capability

def commented_models():
    """Every model declaring a GenericRelation to our Comment. Computed once."""
    return {
        model
        for model in apps.get_models()
        for f in model._meta.get_fields()
        if isinstance(f, GenericRelation) and f.related_model is Comment
    }

register_capability(
    "comments",
    "Comments",
    applies_to=lambda obj, user, **kw: obj.pk is not None,
    supports=lambda model, state, **kw: model in state,
    prepare=commented_models,
    template="comments/section.html",
    order=200,
)
```

Import that module from `AppConfig.ready()`.

## Register your own; core enumerates none

Core renders whatever the registry holds and knows no capability by name. A
capability registered from anywhere but its own app is core knowing contrib by
name — which is the defect this registry exists to remove.

The consequence you get for free: uninstall your package and the section is
simply absent. No guard anywhere else, no dead template reference.

## Two probes, two questions

They look similar and are not.

| | asks | called | for |
|---|---|---|---|
| `applies_to(obj, user)` | does this apply to **this row**? | once per row | the edit form |
| `supports(model, state)` | does this model support it **at all**? | once per model | the matrix |

A model can support a capability that does not apply to a given row — an
unsaved record has nothing to hang a comment on, but `Book` is still
commentable. Answering one question with the other gives a section that appears
on records it cannot work for, or a matrix that lies.

Omit either probe to mean "always".

## `prepare` runs once, not once per model

The matrix asks about every model in the installation. A `supports` probe that
queries would issue one query per model.

```python
prepare=commented_models,                            # one call, returns a set
supports=lambda model, state, **kw: model in state,  # a set lookup per model
```

`prepare()` is called once per capability and its result is handed to every
`supports` call as `state`. If your probe does not need to look anything up,
omit `prepare` entirely.

## Probing by generic relation

The conventional probe: a model opts in by declaring a `GenericRelation` to your
model. That is a **generic** coupling, not a dependency — the consumer writes
the relation in their own models, and your app reads what points at it.

```python
def commented_models():
    return {
        model
        for model in apps.get_models()
        for f in model._meta.get_fields()
        if isinstance(f, GenericRelation) and f.related_model is Comment
    }
```

No registry of "commentable models" to keep in step, and nothing to forget.

**Not `Comment._meta.related_objects`.** That lists the reverse of concrete
foreign keys and contains no `GenericRelation` at all, so it returns an empty
set and your capability silently vanishes from every model. Walk the installed
models and look at their fields, which is the reason `prepare` exists.

## Rules

**Accept `**kw` in both probes.** They are called with keywords and gain
arguments over time; a probe with a fixed signature breaks on the next one.

**Do not query in `applies_to`.** It runs once per record on a list, so a single
query there is a query per row.

**Name it for what it is, not what it draws.** `comments`, not
`comments_section` — the registry key is the capability.

**Ship the template with your package.** A capability whose template lives in
core is not a plugin.

## Verifying

```python
def test_it_does_not_apply_to_an_unsaved_row(capability_registry):
    assert for_object(Book()) == []

def test_the_matrix_asks_once(capability_registry):
    calls = []
    register_capability("comments", prepare=lambda: calls.append(1) or {Book},
                        supports=lambda model, state, **kw: model in state)
    matrix([Book, Region, Note])
    assert len(calls) == 1
```

The second is the one worth copying: it is what stops the matrix from becoming a
query per model as an installation grows.

Use the `capability_registry` fixture so a test's registration does not leak.

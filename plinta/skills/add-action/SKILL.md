---
name: add-action
description: Add a verb beyond Django's add/change/delete/view — export, publish, approve, share. Use when something a user does to a model needs granting separately. Not for narrowing which rows a verb reaches; that is a policy.
---

# Add an action

Django mints `add`, `change`, `delete` and `view` for every model. A fifth verb
is registered once and minted for every DataSource-backed model:

```python
# yourapp/apps.py
def ready(self):
    from plinta.permissions.actions import register_action

    register_action("publish", "publish", filters_rows=True)
```

Registration happens once for the whole project, not per model, because
plinta cannot reach into a consumer's model and add `Meta.permissions`.

## Row action or capability — get this right first

The `filters_rows` argument is the only hard decision here, and it decides
whether a policy may narrow the verb.

**A row action reaches a set of rows**, and that set is genuinely different
from any other verb's. `publish` is one: the articles you may publish are not
the articles you may view. Pass `filters_rows=True`, and write the rule:

```python
class ArticlePolicy(PermissionPolicy):
    view    = Public() | Owner()
    publish = Owner() & HasPerm("editorial.senior_editor")
```

**A capability is a model-level yes or no.** `export` is one: there is no set
of exportable articles distinct from the viewable ones — either you may take
data out of the system or you may not. Pass `filters_rows=False` (the default)
and it composes with `view`'s row filter instead of carrying its own.

Getting this backwards is quiet. Mark a capability as a row action and every
policy that forgets to declare it falls through to the model permission alone,
which is wider than the `view` it should have inherited.

## Silence is not denial

Declaring an action does not narrow it anywhere. A policy that says nothing
about `publish` lets `publish_article` decide it entirely — the same rule as
every other action, and the reason to state it when you mean it:

```python
class ArticlePolicy(PermissionPolicy):
    view    = Public() | Owner()
    publish = view          # as narrow as viewing, said rather than assumed
```

## Rules

**Never register one of Django's four.** `register_action("view", ...)` raises
rather than shadowing — a second definition of `view` would be a second answer
to the question the engine asks most.

**Register from `AppConfig.ready()`, before anything mints.** Minting walks the
registered actions; one registered later exists for nothing until the next
mint.

**Lowercase `[a-z][a-z0-9_]*`.** The codename becomes `{action}_{model}`, and a
name that does not fit makes a permission nobody can type.

**The label is what a permission console shows.** `register_action("publish",
"publish")` yields "Can publish article", so write the verb as it reads in that
sentence — "publish", not "Publishing" or "Publish Article".

**One name for the whole project.** Actions are not namespaced per app; a
second `register_action("export")` raises. If two apps both want it, one
registers it and both use it.

## Minting

`mint_for(model)` creates every registered action's permission for one model,
and returns the ones it created. The layer that knows which models are
registered calls it — this registry knows a model and an action, never which
models exist.

Registering an action after models have been minted means running that again.
Make it a management command in your project rather than a migration: a
migration that mints permissions runs once per database and silently does
nothing on the next action you add.

## Verifying

```python
def test_publish_is_separable_from_change(user, article):
    grant(user, "editorial.change_article")
    assert can(user, "change", article)
    assert not can(user, "publish", article)
```

That is the whole point of registering a verb — if holding `change` implied it,
you did not need one. Test the separation, not the registration.

Use the `action_registry` fixture so a test's registration does not leak.

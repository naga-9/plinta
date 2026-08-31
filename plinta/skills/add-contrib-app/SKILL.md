---
name: add-contrib-app
description: Package a cross-cutting feature as an optional plinta app — attachments, labels, reports, an export format. Use when the feature attaches to other people's models rather than being one app's own screens. Not for a consumer application; that is start-consumer-app.
---

# Add a contrib app

A contrib app is optional, never imported by core, installed by listing it in
`INSTALLED_APPS` and removed by not listing it.

## The shape

```
plinta/contrib/labels/
    __init__.py
    apps.py             # requires / enhances / composes, and ready()
    models.py
    migrations/
    policies.py
    listeners.py
    templates/plinta/labels/
    skills/             # your own extension points, shipped with you
    test_labels.py
```

```python
class LabelsConfig(AppConfig):
    name = "plinta.contrib.labels"
    label = "plinta_labels"          # pinned, so it never collides
    verbose_name = "plinta labels"
    default_auto_field = "django.db.models.BigAutoField"

    requires = ["plinta.permissions", "plinta.events"]

    def ready(self):
        from plinta.contrib.labels import listeners, policies  # noqa: F401
```

## Requires the layers you actually use, and no more

`requires` is checked at boot, so an over-broad list makes your app refuse to
start in a project that would have run it fine. Listing `plinta.pages` because
you ship a seeded page is wrong — a seeder is not an import.

## Sideways imports are forbidden

**A contrib app may not import another contrib app**, except where it declares
`enhances` or `composes` and says what happens without it.

When you need another app's behaviour, invert it through core's events:

```python
# labels/listeners.py
@receiver(signals.object_written)
def sync_derived_labels(sender, instance, **kwargs):
    ...
```

You emit, or you listen. Neither side imports the other, and the app that is
not installed simply never receives.

**`enhances` is for a functional read** — something no event can deliver
because the caller is asking a question, not reacting. Name your substitute
and mean it:

```python
class WorkflowConfig(AppConfig):
    enhances = ["plinta.contrib.audit"]     # history(); empty without it
```

Then import it **inside the function**, never at module scope, and write the
test that asserts so. An `enhances` reached at import time is a dependency
wearing a different word, and it will break the install that does not have it.

## Attach by registration, never by a base class

A mixin puts foreign keys to your tables on the consumer's model, which makes
your optional app **required** for whoever opted in. A `GenericRelation` does
the same thing more quietly.

Bind by content type and let the consumer declare what they have:

```python
Workflow.objects.create(content_type=..., state_field="state")
```

The price is usually one call the consumer makes themselves. That is the
honest cost of not owning the model, and it is cheaper than the trap.

## Say what breaks when you are gone

Uninstalling is a supported state, not a degraded one. Write the sentence, and
make sure the answer is "that feature" and never "the page breaks":

> Absent, records carry no labels. Nothing in core reads one.

## Ship your own skills

If your app registers something a third party can extend — a channel, a guard,
a provider — it ships the skill for it, in `skills/` beside the code. The
skill is discovered through the plugin manifest, so add your directory to
`.claude-plugin/plugin.json` by running `python scripts/build_plugin.py`.

A skill for an app that may not be installed opens by saying so:

> **Requires `plinta.contrib.labels` in `INSTALLED_APPS`.**

## Rules

**Pin `label`.** Two apps called `labels` in one project is a migration
collision, and the loser is whoever named theirs last.

**Namespace your templates** under `plinta/<app>/`. A template at
`labels/chip.html` will be found by whoever else shipped that path.

**Register from your own `AppConfig.ready()`**, everything, always.

**Use only the published extension points.** A private path used by a bundled
app makes the contract fiction — which is why there isn't one.

**Test in the contrib suite** (`pytest -c pytest-contrib.ini`). Core's suite
installs no contrib app, deliberately: a core test that passes only because
your app is installed is a core test that is wrong.

## Verifying

The import-boundary test is the one that matters, and it is already written —
it walks the AST and fails on a core module importing contrib, or a contrib
module importing a peer it did not declare.

Then write the uninstall test, because nobody runs that configuration by
accident:

```python
def test_history_is_empty_without_audit(settings):
    settings.INSTALLED_APPS = [a for a in settings.INSTALLED_APPS
                               if a != "plinta.contrib.audit"]
    assert history(order) == []
```

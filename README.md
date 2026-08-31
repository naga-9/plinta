# plinta

Turn Django models into interactive, permission-aware screens.

Register a model, declare who may see which rows, and compose dashboards from
blocks — without writing a view, a serializer or a template for each one.

- **Your models stay plain Django.** No base class, no mixin, nothing to inherit.
- **Permissions are two-tier.** Django's model permission says *may they at
  all*; a policy you write says *which rows* — and both must hold.
- **Screens are data.** A page is a row, so it is arranged in a browser rather
  than deployed.
- **Dependencies are Django, django-ninja and pydantic.** No CSS framework, no
  grid library, and no front-end major version to chase.

## Try the demo

A bookshop chain, built entirely on the published API:

```bash
git clone https://github.com/naga-9/plinta
cd plinta
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
cd example
python manage.py migrate
python manage.py seed_catalog
python manage.py runserver
```

Python 3.14 or newer. `manage.py` puts the repository root on the path, so the
demo runs against the plinta beside it rather than any other copy on the
machine.

Then sign in at http://127.0.0.1:8000/ as **`mira`** (password `demo`) and open
**Sales**. Sign out, sign in as **`noor`**, and open it again.

Same page, same block, same configuration — different rows. That is the policy
engine scoping through the demo's own idea of who manages which shop, with no
organisation app installed and no filtering written into the screen.

Four logins, four roles: `ada` administers, `mira` and `noor` manage a shop
each, `sam` may only read the catalogue. [`example/README.md`](example/README.md)
says what each one demonstrates and where in the code it lives.

## Installing it in your own project

```bash
pip install plinta-core
```

```python
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "plinta.permissions",
    "plinta.datasources",
    "plinta.renderers",
    "plinta.components",
    "plinta.blocks",
    "plinta.pages",
    "plinta.shell",
    "yourapp",
]

MIDDLEWARE = [
    ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "plinta.shell.middleware.LoginRequiredMiddleware",   # after that one
]
```

`manage.py check` will tell you what is missing. The demo project is a working
version of the whole list — it is in this repository rather than in the wheel,
so clone it to read it.

## The shape of it

Nine layers, each importing only what is below it, enforced by a test rather
than by discipline:

```
utils · dates · forms → events → permissions → datasources
    → renderers → components → blocks → pages → shell
```

Core ships one component and one renderer. Everything else — charts, kanban,
export, comments — is a package that registers through the same door a third
party would use, which is what keeps that door real.

## Documentation

- [`docs/design/SPEC.md`](docs/design/SPEC.md) — the specification: every
  decision, and why it was taken rather than the alternative.
- [`plinta/skills/`](plinta/skills/) — one guide per extension point:
  adding a component, a policy, a computed column, a renderer, a capability.
  A contrib app ships its own beside it, in `plinta/contrib/<app>/skills/`.
- [`example/`](example/) — the demo, and the guard that the public API is real.

Those guides are also a Claude Code plugin, so they load in your own project
rather than only in this repository:

```
/plugin marketplace add naga-9/plinta
/plugin install plinta@plinta
```

Nothing is copied into your project — the manifest points at the files in the
package, so they stay in step with the version you installed.

## Status

Pre-release. The nine core layers are built and tested; the contrib packages
are not yet ported.

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

## Where this comes from

plinta began as the screen engine inside a private commercial application,
where it ran in production for years. **v2 is a ground-up rebuild of that
engine as a standalone library** — the domain model it grew up around is gone,
the layering is enforced by a test rather than intended, and everything
specific to the application it was written for has been removed. Nothing is
ported: v1 is consulted as prior art and then left alone.

**This is a work in progress, and it would be dishonest to present it as a
finished repository.** The rebuild is done layer by layer against a written
specification — [`docs/design/SPEC.md`](docs/design/SPEC.md) — and that
specification describes the **target**, not what exists today. It runs ahead
of the code on purpose: a decision is argued and written down before anything
is built against it. Some sections are complete and tested, some are half
done, and some are not started.

So read the two lists below as a pair: **What it does** is what exists and is
tested today, and **[Future ideas](#future-ideas)** is what the specification
describes and the code does not yet. [Status](#status) is the summary.

## What it does

### Data

- **DataSources** — register a model once; its columns are rows you edit in a
  browser, not code you deploy.
- **Sixteen options per column** — label, order, format, width, precision,
  prefix, renderer, filterability, editability, and how a picker offers its
  choices.
- **Computed columns** — a registered annotation adds a column the model has
  not got, and it sorts and filters like any other.
- **Queryset modifiers** — a named function narrows what a screen reads,
  chosen by whoever built it rather than by whoever looks at it.
- **Traversals** — `author__name` is an ordinary column; the DataSource does
  not care that it crosses a relation.

### Permissions

- **Three tiers, and all three must hold** — Django's model permission says
  *may they at all*, a row policy says *which rows*, a field permission says
  *which columns*.
- **Field permissions are minted from columns** — declaring a column creates
  its `view_` and `change_` permissions, so there is no second list to keep in
  step.
- **Composable row policies** — `Owner("owner") | Public()`, written once per
  model and applied everywhere that model is read.
- **Narrowing happens below the screen** — a block cannot widen what it was
  given, so a misconfigured screen cannot leak.
- **Escalation-safe granting** — nobody can grant a permission they do not
  themselves hold.
- **Capabilities** — permissions that are not about rows, for things like
  exporting or commenting.

### Screens

- **Pages are rows** — arranged in a browser on a twelve-column CSS grid, and
  rendered with no layout JavaScript at all.
- **Blocks** — a component, a DataSource and the config binding them; one
  block can appear on any number of pages.
- **Saved views** — a personal or shared *delta* over a block, so a change its
  author makes later still reaches everyone who did not override it.
- **Filter sets** — a page's filter values, saved whole and optionally shared.
- **Filter bar** — declared per page, with each control's options narrowing as
  the others are chosen.
- **Tabs and detail pages** — the record is in the URL, so a screen is
  something you can send a colleague.
- **One failing block does not take the page** — the slot shows an error and
  its neighbours still draw.

### Writing

- **One write pipeline** — authorise, validate, emit, save, diff, emit. The
  only path by which plinta changes a consumer's data.
- **Inline editing** — edit a cell in a table under the same permissions a
  form would use.
- **Forms** — derived from the DataSource's columns, opened in a dialog from a
  row or drawn on a page.
- **Relation and many-to-many pickers** — a full list under a hundred rows, a
  search-as-you-type above it, decided per column.
- **Three different refusals** — `405` the component does not write, `403` you
  may not, `422` that value will not do.

### Authoring

- **Data Sources screen** — register a model and manage its columns, which is
  also where the permission surface is created.
- **Blocks catalogue and inspector** — the inspector derives its form from the
  component's own schema, so a third-party component gets one free.
- **Page composer** — page settings, place and remove blocks, and arrange the
  grid; dragging is an optional package and typing four numbers is the
  fallback.
- **Django admin as the floor** — every app registers its models, so the
  screens are a convenience rather than the only door.

### Extending

- **Twenty-two extension points in core**, all the same shape: a registry, a
  `register_*` function, and a lookup that says what *is* registered.
- **Components, renderers, policies, annotations, widgets, filters, icons,
  events** — each is a registration, not a subclass.
- **Style packs** — swap plinta's class names for Bootstrap's or your own
  without forking a template.
- **Light and dark** — the viewer's choice, with no colour written outside the
  design tokens.
- **Skills** — one guide per extension point, installable as a Claude Code
  plugin.

### Platform

- **Public data API** — seven endpoints for every DataSource there will ever
  be, generated from the column definitions and gated only by permissions.
- **API keys** — a key resolves to a user, so there is no parallel
  authorisation model to keep in step.
- **Events** — `object_written`, `object_deleted` and their kin, so an app can
  react without anybody importing it.
- **Audit** — every write and who made it, from the API and the UI alike.
- **Notifications** — in-app and email, with per-person preferences.
- **Workflow** — states and transitions per model, with guards.
- **Comments** — threaded, on any model.
- **One command to a working application** — `seed_platform_pages` creates the
  menu and calls whichever apps' seeders are installed.

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

Not on PyPI yet, so install from a checkout:

```bash
git clone https://github.com/naga-9/plinta
pip install -e ./plinta
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

Then one command gives you a working application:

```bash
python manage.py migrate
python manage.py seed_platform_pages
```

It creates the menu and calls whichever per-app seeders are installed, so a
minimal install gets core's screens and nothing else. Install a contrib
package later and re-run it — every seeder is idempotent, so running it again
is always safe.

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

- [`docs/reading-the-code.md`](docs/reading-the-code.md) — **start here with
  the repository open.** Follows one page render through all nine layers,
  then one write, and says where the awkward parts are.
- [`docs/design/SPEC.md`](docs/design/SPEC.md) — the specification: every
  decision, and why it was taken rather than the alternative. Organised by
  decision, so it answers questions rather than introducing the code.
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

## Future ideas

Written down so the gaps are visible rather than discovered. Several are
specified in [`SPEC.md`](docs/design/SPEC.md) and simply not built yet.

- **Configuration lifecycle** — pages and blocks are database rows with no git
  history and no path from a development machine to production. An export and
  import, so a dashboard can be reviewed in a pull request. *The largest gap
  in the design, and §16 says so.*
- **More components** — charts, kanban, gantt, pivot, KPI, gauge, detail card,
  repeater, text and alert. Three of fourteen exist.
- **Export** — the same table as Excel, CSV or PDF, through the renderer
  registry rather than a second data path.
- **Tenancy** — an organisation package supplying company, site and business
  unit, with the permission engine scoping through it and never importing it.
- **Labels, attachments, checklists and reports** — the remaining contrib
  packages.
- **Scopes on an API key** — narrowing a key *below* what its user may do,
  never above.
- **Rate limiting** — page caps decide how fast today; a rate limit is the
  other half.
- **Async and long-running work** — a report or an export that takes a minute
  should not hold a request open.
- **A published package** — the distribution is named `plinta-core` and is
  not on PyPI; installing means cloning. Publishing it is a release decision,
  not a code one.

Ideas are welcome. Something that would make plinta name a domain concept —
an invoice, a ticket, a customer — is very likely a contrib package rather
than a core feature, and the [three tests in
`SPEC.md`](docs/design/SPEC.md) say which.

## Status

**Pre-release, and moving.** The nine core layers are built and tested, with
four suites: core, contrib, a real-browser suite and the demo.

| | |
|---|---|
| Core layers | complete |
| Authoring screens | complete — data sources, blocks, pages |
| Write path, saved views, filter sets | complete |
| Public API | complete |
| Seeders | 3 of 8; the rest wait on their packages |
| Components | 3 of 14 |
| Contrib packages | 6 of the 12 specified, plus three extras |
| Configuration lifecycle | not started |

The API is not stable and the schema still moves. Read
[`SPEC.md`](docs/design/SPEC.md) before depending on anything.

# Plinta v2 — functional & technical spec

The specification for the rebuild. One file, so it cannot drift against itself.

**How to read it.** Parts I and II are the build: sections 3–10 are the nine layers in the order they get written, each stating its responsibility, its public API, what it may import, and what it must not know. Part III is what ships on top of them. Part IV is what cuts across all of them. Part V is reference — conventions, the per-feature decision ledger, what is deferred, the build sequence with its done-when conditions, and the decision records.

**Every decision in this document is taken.** Nothing is described as an open question and nothing is hedged. What is not being built is in §22, once, with the use case that would bring it back.

Usage figures come from a live v1 install: 44 DataSources, 279 fields, 54 Blocks, 36 Pages. "0 uses" is evidence, not proof.

**Numbering.** Every section and subsection is numbered, and `§N.M` addresses one directly. The two exceptions carry their own identifiers instead: the contrib packages in §14.6 are named after the package, and the decision records in §24 are cited as *ADR 0004 (§24)*.

## Contents

**Part I — Foundations**

| § | Section |
|---|---|
| 1 | [Purpose and scope](#1-purpose-and-scope) |
| 2 | [Architecture](#2-architecture) |

**Part II — The layers, in build order**

| § | Section |
|---|---|
| 3 | [Layer 1 — utils, dates, forms](#3-layer-1-utils-dates-forms) |
| 4 | [Layer 2 — events](#4-layer-2-events) |
| 5 | [Layer 3 — permissions](#5-layer-3-permissions) |
| 6 | [Layer 4 — datasources](#6-layer-4-datasources) |
| 7 | [Layers 5–6 — renderers and components](#7-layers-56-renderers-and-components) |
| 8 | [Layer 7 — blocks](#8-layer-7-blocks) |
| 9 | [Layer 8 — pages](#9-layer-8-pages) |
| 10 | [Layer 9 — the shell](#10-layer-9-the-shell) |

**Part III — What ships**

| § | Section |
|---|---|
| 11 | [The component catalogue](#11-the-component-catalogue) |
| 12 | [The authoring screens](#12-the-authoring-screens) |
| 13 | [Framework pages and seeding](#13-framework-pages-and-seeding) |
| 14 | [Contrib packages](#14-contrib-packages) |

**Part IV — Cross-cutting**

| § | Section |
|---|---|
| 15 | [The API](#15-the-api) |
| 16 | [Configuration lifecycle](#16-configuration-lifecycle) |
| 17 | [Assets and theming](#17-assets-and-theming) |
| 18 | [Extension points](#18-extension-points) |
| 19 | [Settings](#19-settings) |

**Part V — Reference**

| § | Section |
|---|---|
| 20 | [Conventions](#20-conventions) |
| 21 | [Feature decisions](#21-feature-decisions) |
| 22 | [Deferred and deleted](#22-deferred-and-deleted) |
| 23 | [Build order](#23-build-order) |
| 24 | [Decision records](#24-decision-records) |
| 25 | [Skills](#25-skills) |

---

# Part I — Foundations

## 1. Purpose and scope

Plinta turns Django models into interactive, permission-aware screens.

A consuming project defines plain Django models. Plinta registers them, renders them as configurable screens, enforces row- and field-level access on every read and write, and lets a non-developer rearrange those screens at runtime without a deployment.

### 1.1 Why it exists

Read-only dashboards are a solved problem — Metabase and Superset do it better than plinta ever will, over raw SQL.

Plinta exists for the **write path**. A cell is editable, an edit is validated by the model layer, a state transition is guarded by a permission policy, and every change is attributable. No BI tool crosses that line, because crossing it means living inside the ORM.

If a project only needs to look at data, it should not use plinta.

### 1.2 What plinta is not

| Not | Why |
|---|---|
| An app generator | Models stay plain Django. Plinta never requires a base class on a consumer's model, never generates model code, and never owns the schema. |
| A BI tool | It renders a registered ORM model, not arbitrary SQL. No query builder, no semantic layer, no warehouse connectors. |
| No-code | Consumers configure the *surface* — screens, columns, filters, permissions. Developers define the *schema* — models, fields, migrations. That line is deliberate and is not crossed. |
| A CMS | Pages compose data views, not authored content. |
| Multi-tenant by default | Tenancy is a contrib concern. Core has no notion of a company, site or tenant. |

### 1.3 Non-goals

- Supporting databases Django does not support.
- Generating migrations or model code on a consumer's behalf.
- Runtime schema editing. Adding a field is a code change and a migration, always.
- Replacing Django admin. Plinta is for the screens end users see; admin remains for staff data entry.

### 1.4 Intended consumers

A Django project with an existing, meaningful domain model that needs screens over it — including permissioned editing, state transitions and an audit trail — and wants to compose those screens in a browser rather than in templates.

**Plinta is built to carry several such applications, not one.** A portfolio and trading platform, a project management system, a CRM, a task tracker — each is its own Django project with its own models, its own repository and its own release cycle, installing plinta as a dependency. None of them lives in this repository.

That is why plinta ships **no domain application of its own**. The moment one is bundled it stops being a consumer and becomes a privileged insider: it reaches past the published API because it can, and the API rots without anyone noticing. `example/catalog` is the guard — a full consumer built only on what a third party can use, and the reason `actions` was removed rather than kept as a favoured tenant (ADR 0008 (§24)).

A consumer application may depend on **anything**: any core layer, any contrib package, several at once. The layer rules constrain what plinta ships, not what is built on it.

### 1.5 The reader this documentation assumes

A Django developer who has not seen plinta before. Every section states decisions, not history. Where a decision has a non-obvious consequence, the consequence is stated; the debate that produced it is not.

**§24 is the exception.** A decision record carries its context and, where a decision was later revised, what was wrong with the first one — because a reader who does not know why a rule exists will re-derive the thing it forbids.

## 2. Architecture

### 2.1 Governing principle

> **Core ships the contract plus one reference implementation. Contrib ships the rest.**

Corollary, and a review test: if core contains two implementations of anything, one of them belongs in contrib.

### 2.2 Core vs contrib: three tests

A package belongs in core only if it passes all three.

**1. Sentence test.** Remove it. Can core still *turn Django models into interactive, permission-aware screens*? If yes, it is contrib.

**2. Noun test.** Core defines **mechanism** nouns: DataSource, Block, Page, Component, Policy, Rule. Contrib defines **domain** nouns: Comment, Label, Attachment, Company, Site, Report, Notification. A model that names something existing in the real world of a business is not core.

The test says where it is *not*, not where it goes. Below contrib there is a third home: a **consumer app**, outside plinta entirely. The line between them is facility and domain. `comments`, `labels`, `attachments` and `checklist` are domain nouns that any application wants — facilities, so contrib. A task tracker with `responsible`, `urgency`, `followers` and `blocked_by` is one application's domain, so a consumer app (ADR 0008 (§24)).

**3. Import test.** Core is a **closed set**. No core module may import from `plinta.contrib`. Enforced by `tests/test_import_boundary.py`, which walks the AST of every core module — not by discipline.

Corollary: a package that only *reacts* to core events is contrib by construction.

#### Applying them

**Apply the sentence test to the sentence, not to a paraphrase.** Every word in it is load-bearing, and *interactive* is the one most easily dropped. `SavedView` and `FilterSet` were once moved to contrib on the reasoning "core can render a screen without them" — which is a paraphrase. Against the actual sentence they pass: a screen that forgets the columns you chose, the filters you set and the order you arranged them in is not interactive, it is a report you reconfigure on every visit. A dashboard platform where nobody can save a view is not a smaller platform; it is a demo (ADR 0004 (§24), revised).

The three tests have never actually disagreed in this document. Where one appears to, check that it was applied to the whole sentence before concluding they conflict.

### 2.3 Layers

Dependencies flow in one direction only. A layer may import from any layer below it and must not import from any layer above it or from contrib.

```
                    ┌──────────────────────────────┐
   contrib          │  organization  workflow      │
   (any core layer; │  audit  notifications        │
    another contrib │  comments  labels            │
    only when       │  attachments  checklist      │
    declared, §2.5) │  reports  export  api        │
                    │  components.*                │
                    └──────────────┬───────────────┘
                                   │ may import ↓
  ┌────────────────────────────────┴───────────────┐
  │ 9  shell         base template, sidebar, auth, theming
  │ 8  pages         composition, grid, menu, filter bar
  │ 7  blocks        saved component configs, write pipeline
  │ 6  components    rendering contract + registry (+ table)
  │ 5  renderers     output contract (+ HTML)
  │ 4  datasources   model registry, field config, querysets
  │ 3  permissions   rule engine, policies, field gating
  │ 2  events        the signal bus
  │ 1  utils         API envelope, request parsing
  │    dates         relative-date resolution
  │    forms         schema-derived forms and coercion
  └────────────────────────────────────────────────┘
```

Eleven packages across nine layers: layer 1 carries three that import nothing of plinta's, and `renderers` and `components` are numbered separately because the second may import the first.

`components` sits **above** `renderers` and may import it — a component uses the shared format helpers, so a date renders identically in HTML and in a spreadsheet. `renderers` must never import `components`: a renderer receives rows and fields, never a component.

### 2.4 Assignment

**Core**

| Package | Responsibility |
|---|---|
| `utils` | API envelope, request parsing, shared primitives |
| `dates` | relative-date resolution (`last_30_days`, `current_month`, …) |
| `forms` | schema-derived form fields, widget selection, POST coercion (§3.3) |
| `events` | the signal bus and the core event vocabulary |
| `permissions` | rule engine, `Owner` / `Public` / `InstancePerm`, field-level gating, the permission console |
| `datasources` | the model registry — DataSource, DataSourceField, queryset services |
| `components` | the rendering contract and registry, plus `table_plinta` |
| `renderers` | the output contract, plus HTML |
| `blocks` | saved component configs, `SavedView`, and the write pipeline |
| `pages` | composition, grid, menu, `PageFilter` (the filter bar), `FilterSet`, `PageFilterPreference` |
| `shell` | base template, sidebar, auth views, `LoginRequiredMiddleware`, design tokens |

**Contrib**

| Package | Ships |
|---|---|
| `organization` | Company, Site, BusinessUnit, user grants, fiscal calendar, scope-provider policies |
| `workflow` | Workflow, State, Transition, and the guard registry — no base class |
| `audit` | AuditLog — a pure listener |
| `notifications` | Notification, EmailQueue, preferences — a pure listener |
| `comments` | Comment and its section component |
| `labels` | Label, LabeledItem and its section component |
| `attachments` | Attachment and its section component |
| `checklist` | ChecklistItem |
| `reports` | ReportDefinition, ScheduledReport |
| `export` | Excel, PDF and email renderers; the export endpoint |
| `api` | the public data API, API keys, the OpenAPI spec |

Eleven packages, plus twelve component packages under `components.*`. None is required: an installation with none of them is a working plinta that shows tables.
| `components.*` | twelve components, named `capability_implementation` (§11) |

### 2.5 Dependency rules

**Downward — contrib may depend on core.** Declared on the `AppConfig` as `requires`, validated by a `django.core.checks` function at startup. Missing requirement is an error, not a runtime surprise.

**Sideways — contrib may depend on contrib, but only by declaration.** An undeclared `plinta.contrib.x` importing `plinta.contrib.y` is a test failure. A declared one is ordinary.

This follows `django.contrib`, which does exactly this and is the only large precedent worth copying:

| Django | Shape |
|---|---|
| `admin` → `auth`, `contenttypes`, `messages`, `sessions` | module-scope imports, `admin.E402`–`E409` at boot |
| `flatpages` → `sites` | `ForeignKey` **and** `dependencies = [("sites", "0001_initial")]` |
| `auth`, `redirects`, `sitemaps`, `syndication` → `sites` | consumed through `get_current_site()`, which substitutes when absent |
| `AUTH_USER_MODEL`, `SITE_ID` | swappable through settings |

Django has no rule against cross-references. It has a rule that they be **declared and checked**, or **degrade through a named substitute**. That is the rule here too.

#### Three kinds of coupling

They look alike in a grep and are not. The kind decides which declaration applies.

| Kind | Example | Declaration |
|---|---|---|
| **Behavioural** — "do something when this happens" | notify on save | **None.** Invert through the core event bus: `workflow` emits `state_changed` and knows nothing about who listens. |
| **Generic** — a reverse accessor | `GenericRelation('labels.LabeledItem')` | **None.** Not a dependency: the FK points the other way through contenttypes. Delete the accessor and nothing changes. |
| **Structural** — schema | a base class, a `ForeignKey`, a migration `dependencies` entry | **`composes`** — no event bus inverts a schema, so it is declared and checked instead. |
| **Functional** — calling another package's API | rendering a report to xlsx | **`enhances`**, with a named substitute. |

Conflating the first two with the third is how a package acquires a hard dependency while its documentation claims the coupling is optional (ADR 0008 (§24)).

#### The two declarations

Both are stated on the `AppConfig`, checked at startup, and listed on the package's own page.

| Relationship | Meaning | Bar | On failure |
|---|---|---|---|
| `enhances` | Works without the other, better with it | **Must name a substitute with the same interface** | Informational check |
| `composes` | Cannot be installed without the other — a base class, an FK, a migration dependency | The coupling must be structural, not merely convenient | Error at boot |

**`enhances` means substitute, not skip.** The model is `django.contrib.sites`:

```python
def get_current_site(request):
    if apps.is_installed("django.contrib.sites"):
        from .models import Site
        return Site.objects.get_current(request)
    return RequestSite(request)          # same interface, degraded
```

Callers never branch. A guard that makes a feature silently vanish is not an `enhances` relationship — it is an undeclared dependency with a `try` around it. Every `enhances` in this document names what stands in: `renderers` falls back from `xlsx` to `html` (§7.1), kanban renders a column without chips, a page renders a slot without its component.

`composes` is the honest declaration for a schema-level dependency, not a failure. `flatpages` is a good app and it cannot exist without `sites`.

#### Every declared relationship in the project

The register. Nowhere else in this document counts them; a count in two places is a count that drifts.

| Declarer | On | Kind | Substitute when absent |
|---|---|---|---|
| `reports` | `export` | `enhances` | the HTML renderer — the report runs to screen (§7.1) |
| `workflow` | `audit` | `enhances` | an empty transition history (§14.6) |
| `components.kanban` | `labels` | `enhances` | a card with no label chips (§11.2) |
| `components.kanban` | `workflow` | `enhances` | grouping by an ordinary field, with no state columns and no drag-to-transition (§11.2) |

**No shipped package declares `composes`.** That is a result, not a rule: the one structural cross-contrib dependency the previous design had was `actions` → `workflow`, and `actions` is not shipped (ADR 0008 (§24)). A `composes` appearing later is legitimate — it constrains the build order (§23.1) and must be added here.

### 2.6 Consequences

**Core's dependencies are Django, django-ninja and pydantic.** `openpyxl` and `pandas` leave with `export`, `Pillow` with `attachments`, `django-ckeditor-5` with `comments`, `weasyprint` with PDF. Nothing native, nothing heavy.

**Core's front end is the shared client plus the shell's `theme-toggle.js` and generated `tokens.js`.** It ships **no CSS framework** (§10.8) and **no grid library** (§11.2): the styling is plinta's own, built from `tokens.json`, and core's `table_plinta` is server-rendered HTML. Its vendored libraries are Bootstrap Icons — the icon set alone, which needs none of Bootstrap's CSS — Tom Select, Luxon and GridStack, served from `static/`, never a CDN (§17). Tabulator ships with `contrib.components.table_tabulator`; Plotly, WebDataRocks, Flexmonster and jsGantt with theirs.

**What a viewer loads is close to nothing.** Layout is CSS grid driven by the stored position, so viewing a page needs no layout JavaScript; GridStack loads only in edit mode. **Core carries no front-end major-version upgrade at all** — every vendor that could impose one travels with a component someone chose to install.

**A minimal install is eleven packages** — the core layers and nothing else. A full install adds eleven contrib packages and ten contrib components, so thirty-two. Both ends are supported configurations and both are exercised in CI (§20).

### 2.7 The core data model

Eleven models. Everything else is contrib.

```
   ContentType (django)
        │
        ▼
   DataSource ───────────┐
        │                │
        ▼                ▼
  DataSourceField      Block ◄────── PageBlock ──────► Page
                         ▲                               │
                         │                               ├──► PageFilter
                     SavedView                           ├──► FilterSet
                                                         ├──► PageFilterPreference
                                                         └──► MenuGroup ──► MenuSection
```

Read the arrows as "points at": `PageBlock` places a `Block` on a `Page`; `SavedView` is a delta over a `Block`; `FilterSet` and `PageFilterPreference` hang off a `Page`.

| Model | Is | Key |
|---|---|---|
| `DataSource` | a registered Django model | content type |
| `DataSourceField` | one column's behaviour | data source + field path |
| `Block` | a saved component config | name, per owner |
| `SavedView` | a delta over a block's config | block + owner + name |
| `Page` | a composition of blocks | slug, per owner |
| `PageBlock` | a block placed on a page at a grid position | page + block |
| `PageFilter` | a control on a page's filter bar | page + field path |
| `FilterSet` | a saved set of filter-bar values | page + owner + name |
| `PageFilterPreference` | one user's remembered filter-bar state | page + user |
| `MenuGroup`, `MenuSection` | navigation placement | name |

`SavedView`, `FilterSet` and `PageFilterPreference` are core on all three tests. They name no real-world object; each is a **delta over a core model** rather than a thing in its own right; and screens that forget how a user arranged them are not interactive, which is what the product sentence promises (ADR 0004 (§24), revised).

### 2.8 Relationships that matter

**`Block` → `DataSource`** is a foreign key. A block cannot exist without the model it reads.

**`PageBlock`** is a composition join. It travels with its page, is never independently shareable, and carries the grid position — so the same block may appear on several pages at different sizes.

**`Page` → `Block`** resolves by **foreign key**, never by name. Name resolution was a defect: names are unique only per owner, so it could reach the wrong block.

**No core model has a foreign key into contrib.** Every contrib attachment is a generic relation, which is why no migration in core depends on a contrib app, and why contrib apps can be added and removed without migrating core.

### 2.9 Ownership and sharing

`Block` and `Page` carry an owner.

| Owner | Visible to |
|---|---|
| `null` | everyone with the baseline model permission — **public means everyone** |
| a user | that user, plus anyone granted an instance permission |

Sharing is additive: an object is owned *and* shared, and sharing never demotes the owner.

Because names are unique per owner rather than globally, instance permissions are keyed by primary key. Name-keying would let a grant on a public object leak to a same-named private one.

### 2.10 Config is a validated JSON document

A `Block.config` is JSON, validated against its component's pydantic schema with `extra='forbid'`. A typo is rejected at save time rather than ignored at render time.

The schema belongs to the component, so core never enumerates config keys and a new component adds none.

### 2.11 Consequences of config-as-data

Screens are rows, which is what makes runtime authoring possible. It also means the schema of a screen is not in migrations and not in git — see §16, which is the answer to that.

---

---

# Part II — The layers, in build order

## 3. Layer 1 — utils, dates, forms



Build **layer 1**. Nothing else can start until this is settled.

Three packages at the bottom of the stack.

**May import:** nothing from plinta.
**Must not know:** anything about plinta's own models — no DataSource, no Block, no policy, no component. A layer-1 module is testable with plinta uninstalled.

### 3.1 `utils`

130 lines today, and most of it survives.

| Holds | Why |
|---|---|
| the API envelope — `json_response` | one response shape for the private transport, so its one client parses one thing (§15.2) |
| `parse_request(request, schema)` | request → validated parameters, shared by every router |
| `schemas.py` — `FilterValuesAdapter` | shared pydantic adapters for filter-style JSON |

**The rule for admission:** a module belongs here only if it would still make sense in a project that had never heard of plinta. Anything that knows what a DataSource is belongs a layer up. `utils` is imported by every other layer, so a domain concept smuggled in here makes the layering meaningless.

**`HTML_KWARGS` is deleted.** `{'tags': ['html'], 'include_in_schema': False}` exists only to hide HTML-fragment endpoints from the OpenAPI schema. Fragments move to plain Django views (§15), so there is nothing to hide and no flag to remember.

**`FilterValuesAdapter` loses one of its three consumers** — `DataSourceField.editor_queryset_filter` is dropped (§6.7). It still serves `Block.base_filter` and `ScheduledReport.filters`.

### 3.2 `dates`

Calendar arithmetic, and nothing that knows what a company is.

**Named relative ranges** resolved against today: `past`, `current_month`, `next_month`, `next_2_months`, `next_3_months`, `next_6_months`, `next_12_months`. Each resolves to a `Q` for a named date field, so a filter declares `due_date` + `current_month` and neither the filter nor the caller computes dates.

### 3.3 `forms`

A pydantic schema in, a rendered form and a parsed dict out. Extracted from `components/block_settings/api.py`, where ~205 of 667 lines are a generic engine wearing a component's name (§8.9).

| Function | Does |
|---|---|
| `fields_for(schema)` | walks `model_fields`, yields a `FormField` descriptor per entry |
| `widget_for(annotation)` | maps a python annotation to an input type |
| `parse(schema, data)` | submitted values → dict, validated by the schema itself |
| `register_widget(schema, field, template)` | the override registry — a bespoke editor for one field (§12.3). Keyed by the schema **class**, so a rename cannot orphan an override and a misspelled field raises at import |

**Why it is layer 1.** It knows pydantic and HTML and nothing about plinta: no DataSource, no Block, no permission. It would make sense in a project that had never heard of plinta, which is §3.1's admission test.

**Who uses it.** The block inspector, page settings, `FilterSet` editing, and any contrib package editing a schema-backed config. Four hand-built forms become one declaration each.

**What it does not do.** It does not decide *whether* a field may be edited. Field permissions are §5.7's job, resolved a layer up and passed in as the set of editable names — a form engine that consulted permissions would be a form engine that knows what a user is.

### 3.4 Splitting `organization/utils.py`

273 lines, and the split is not even:

| Lines | What | Goes to |
|---|---|---|
| 15–75 | `RELATIVE_DATE_OPTIONS`, `_month_start`, `_month_end`, `_add_months`, `resolve_relative_date_q` | **core `dates`** (~60 lines) |
| 76–273 | `get_current_fiscal_period`, `get_fiscal_month_order`, `get_fiscal_context`, `sort_by_fiscal_month`, `resolve_fiscal_placeholders` | **`contrib.organization`** (~200 lines) |

A fiscal year belongs to a legal entity — it fails the noun test. Calendar arithmetic does not.

### 3.5 The problem the split does not solve

Splitting the module is the easy half. Seven modules import from it, and two of them are **core importing what becomes contrib**:

| Importer | Imports | After the split |
|---|---|---|
| `components/base.py:135` | `resolve_relative_date_q` | core → core ✅ |
| `datasources/api.py:18` | `get_fiscal_context`, `resolve_fiscal_placeholders` | **core → contrib ❌** |
| `pages/views.py:16` | `get_fiscal_context`, `resolve_fiscal_placeholders`, `RELATIVE_DATE_OPTIONS` | **core → contrib ❌** |
| `components/charts/component.py:20` | three fiscal helpers | contrib → contrib (chart is contrib) — needs §4-style routing |
| `components/pivots/component.py:25` | `get_fiscal_context` | as above |
| `reports/builder.py:318,853` | fiscal helpers | contrib → contrib — as above |

So §3.4's claim that the fiscal split resolves the coupling is **incomplete**. Moving the code does not stop core calling it.

### 3.6 The placeholder registry

**It lives in `utils`, not `dates`.** Its own examples are `__CURRENT_USER__` and `my_watchlist`; only some tokens are date-shaped, and a package named `dates` holding a resolver that returns a list of instrument ids is the drift §10.5 renames `deployment_env` to avoid. `dates` keeps what is calendar arithmetic.

What those two core modules actually do is resolve **magic tokens inside filter values** before querying — `__CURRENT_FISCAL_YEAR__` becomes 2026, `__CURRENT_MONTH__` becomes 8.

That is a generic mechanism wearing a fiscal costume. Core owns the registry; providers register into it:

```python
register_placeholder('today',            lambda ctx: date.today())
register_placeholder('current_month',    lambda ctx: date.today().month)
# contrib.organization, at ready():
register_placeholder('current_fiscal_year', lambda ctx: fiscal_year_for(ctx.user))
```

Core then calls `resolve_placeholders(values, ctx)` and never imports a fiscal helper. A token with no registered provider is **left untouched** — not silently blanked, which would widen a filter.

**Each layer reports its own unresolved tokens.** `utils` supplies `unresolved(values)`; the check that walks stored configuration belongs to the layer that owns it, because `utils` cannot read a `Block` and `permissions` (layer 3) cannot import one either:

| Owns the config | Checks |
|---|---|
| `blocks` | `Block.base_filter`, `create_defaults` |
| `pages` | `PageFilter` values, `FilterSet.values` |
| `contrib.reports` | `ScheduledReport.filters` |

This is the same shape as the shell registering its own middleware check (§10.4): §5.13's list is `permissions`' checks, not a place other layers file theirs.

These read rows, so they run as a management command rather than a `django.core.checks` function — a system check runs during `migrate` against a database that may not have the tables yet.

#### Ranges and placeholders are two registries

They look like one and are not, which §20.4's test settles: a **range** takes `(field, today)` and returns a `Q` over a date field; a **placeholder** takes a context and returns a value. Neither the input nor the output shape matches, so they are separate — `dates.register_range` and `utils.register_placeholder`.

Both are extension points. `contrib.organization` registers fiscal ranges into the first and fiscal tokens into the second, and core imports no fiscal helper either way.

So the design carries **four** registries, not three: annotations (§6.10), queryset modifiers (§6.4), placeholders (§3.6) and ranges.

#### One placeholder registry, three consumers:

- filter values (`__CURRENT_FISCAL_YEAR__`, today's `resolve_fiscal_placeholders`)
- `create_defaults` on a block (`__CURRENT_USER__` today — §6 records that it should become named placeholders)
- the filter UI's list of offered ranges — fiscal options appear only when their provider is installed

Three mechanisms today, one after. And it is the same shape as every other extension point: registered by name, never an expression.

#### Consumers register their own

Registration is code, the name is config — the same door core and contrib use, so nothing is privileged:

```python
# a consumer's placeholders.py — autodiscovered
@register_placeholder('current_quarter')
def current_quarter(ctx):
    return quarter_of(date.today())

@register_placeholder('my_watchlist')
def my_watchlist(ctx):
    return list(ctx.user.watchlists.values_list('instrument_id', flat=True))
```

A page filter, a `FilterSet` or a scheduled report then writes `{"date": "__CURRENT_QUARTER__"}` and it resolves at query time.

#### Three boundaries

These are what keep a registry from becoming a language.

**1. A token supplies a *value*, never a field path and never an operator.** `{"date": "__CURRENT_QUARTER__"}` is legitimate; a token expanding into `date__gte` is not. The configuration declares *what* is filtered and *how*; the token declares only *with what*. This is what makes a token incapable of widening a filter into fields its author never named.

**2. The resolver receives a context, so tokens may be user-scoped.** `__CURRENT_USER__` already is, and `my_watchlist` above depends on who is asking. That is the point — and it means a token is evaluated per request and never cached globally.

**3. The returned type must match the declared lookup.** A token returning a list against an `exact` lookup is a configuration error, caught at validation rather than at query time.

#### Where tokens may appear

Filter-style dicts only:

- page filter values
- `FilterSet.values`
- `Block.base_filter`
- `ScheduledReport.filters`
- `create_defaults`

Not in block config generally, not in column definitions. Those five already share `FilterValuesAdapter` (§3.1), so there is one place to enforce it.

### 3.7 Decisions

| Item | Decision |
|---|---|
| API envelope, `parse_request`, shared schemas | keep in `utils` |
| `HTML_KWARGS` | **drop** — fragments leave the OpenAPI framework (§15) |
| Relative date ranges and `resolve_relative_date_q` | **→ core `dates`** |
| Fiscal calendar, fiscal context, fiscal month ordering | **→ `contrib.organization`** |
| `resolve_fiscal_placeholders` as a fiscal-specific function | **replaced** by the generic placeholder registry |
| `__CURRENT_USER__` magic string | **→ the same registry**, as a named placeholder |
| An unresolvable token | left untouched **and reported**, never blanked |
| Who may register a token | core, contrib and consumers — the same door |
| Where the placeholder registry lives | **`utils`** — most tokens are not dates |
| Named date ranges | a **second** registry, in `dates`; `(field, today) → Q` |
| What a token may return | a **value** only; never a field path, never an operator |
| Where tokens are honoured | filter-style dicts only (five call sites, one validator) |


## 4. Layer 2 — events



The signal bus. Anyone may emit — core, a contrib package, a consumer's own importer (§4.5); what is fixed is the vocabulary, not who uses it.

It exists to remove the coupling that is **behavioural** — "do something when this happens" — which is the kind that never needed an import in the first place. All four sideways imports in the current tree are that kind, and all four point at `notifications`. Coupling that is structural or functional is declared instead, not evented away (§2.5).

**May import:** `utils`.
**Must not know:** that any listener exists. No core module imports a listener, checks whether one is installed, or branches on the result of an emit.

### 4.1 The vocabulary

Five signals. **Core declares all five, including the two it never emits.**

That looks wrong and is load-bearing.

**A signal lives in the lowest package every party can import.** The emitter and its listeners are the parties; the question is never which layer the emitter sits in.

| Signal | Emitter | Listeners | Lowest common package |
|---|---|---|---|
| a consumer's `order_shipped` | the consumer | the consumer | **the consumer** — keep it private |
| `state_changed` | `contrib.workflow` | `contrib.audit`, `contrib.notifications` | **core** |
| `comment_posted` | `contrib.comments` | `contrib.notifications`, `contrib.audit` | **core** |

A consumer's own event has one party wearing both hats, so it needs no mechanism at all — a plain `django.dispatch.Signal` in their own app (§4.5). `state_changed` has three parties in three sibling packages that may not import each other, so the only place all three reach is core. **A contrib package with an event only it consumes keeps that private too**; nothing pushes a signal into core except a listener that cannot otherwise reach it.

**Core may hold a signal it never emits only if the payload needs nothing core does not already have.** `state_changed` passes because states cross as string codes (§4.8), so core references no `Workflow` model. One carrying a `WorkflowState` instance would fail — and would then have to stay private, taking its listeners' independence with it.

The same shape as a registry (§20.4): core owns the vocabulary, contrib owns the implementation.

| Signal | Emitted by | Payload |
|---|---|---|
| `object_writing` | `blocks` write pipeline, pre-save | `obj`, `mode`, `fields`, `actor`, `source` |
| `object_written` | `blocks` write pipeline, post-M2M | `obj`, `mode`, `changes`, `actor`, `source` |
| `object_deleted` | `blocks` write pipeline | `obj`, **`pk`**, `actor`, `source` |
| `state_changed` | `contrib.workflow` | `obj`, `from_state`, `to_state`, `actor`, `comment`, `metadata`, `source` |
| `comment_posted` | `contrib.comments` | `obj`, `actor`, `body`, `metadata`, `source` |

A listener imports the signal from **core**, never from the emitter, so `audit` observing a workflow transition creates no dependency between the two apps.

**Every signal carries the same envelope — `obj`, `actor`, `source`** — and adds its own payload on top. A listener subscribing to several reads one shape; without that it branches on which signal fired before it can find the row or the actor.

`source` names the path that performed the write. Three exist today — `block_edit`, `block_delete`, `permission_admin` — and v2 adds at least `api` and `import`. It answers what the diff cannot: the same actor changing the same field means something different through the UI, the nightly import, or the API.

An earlier draft of this table gave `comment_posted` neither `source` nor `obj`, naming its row `target` instead. Both were composition oversights rather than decisions, and each forced a listener to special-case exactly one signal.

`object_deleted` carries `pk` separately because Django's `Collector.delete` sets the primary key attribute to None on the instance. By the time a listener runs, `obj.pk` is gone — so the caller captures it before deleting, or the audit trail cannot say what was deleted.

The payload carries **no request**. That is a web concern, and an event must be emittable from a management command. `actor` and `source` therefore default, so an emit from a script needs neither.

**The sender is the model class.** `emit_written(book, …)` sends with `sender=Book`, so a listener interested in one model filters at connection time — `@receiver(object_written, sender=Book)` — rather than checking the type of every write in the system.

### 4.2 `object_written` carries the diff

`changes` is `{field_name: (before, after)}`, computed by core.

This is the load-bearing decision of the event model. Audit writes one row per changed field, which needs a pre-save baseline; if it had to take that snapshot itself it would need a hook inside the write path and would not be a listener.

It does not, because **core performs the write and therefore already knows what changed.** Computing the diff is a statement about the write, not a service rendered to audit. Notifications reads the same payload; labels reads the label field from it.

Emission is skipped when a signal has no receivers, so the diff costs nothing on a minimal install.

**Only fields the write touched, and only those that actually changed.** A resubmitted identical value produces no entry and therefore no audit row — today's behaviour, kept.

The trade, stated so it is not filed as a bug: fields the *model* changes on its own — `auto_now`, values set inside `save()`, computed columns — do not appear, because they were never snapshotted. Capturing them would mean snapshotting every field on every write, which is largely `updated_at` noise.

**Create carries the same shape:** `changes = {field: (None, value)}` with `mode='create'`. The payload stays uniform; the listener decides what to do with it.

### 4.3 When it fires

**After M2M, not after `save()`.** M2M cannot be applied until the instance has a primary key, and a `changes` dict omitting M2M would be a lie. The current pipeline already proves the position: `apply_m2m_updates` (11) is followed by `sync_labels` (12), `fire_notifications` (13) and `audit_changes` (14) — those three stages are the listeners in disguise, and the emit point is where they sit.

**Inside the transaction.** The two consumers want opposite things: audit wants atomicity, so a row cannot be orphaned from the change it records; notifications want post-commit, so nobody is emailed about a write that rolled back.

One signal, fired in-transaction, and **a listener needing post-commit semantics wraps its own work in `transaction.on_commit`**. The choice sits with the listener that has the requirement, and it is the idiomatic Django answer.

### 4.4 Plinta emits for writes plinta performed

**Not a `post_save` hook.** Hooking `post_save` would fire for migrations, fixtures, shell sessions and consumer code — with no actor and no source — producing a trail that looks complete while being full of anonymous rows.

So the boundary is: **plinta audits what plinta mediates.** Every screen and every API write is covered, for a consumer's models as much as plinta's own. A consumer calling `obj.save()` in their own code emits nothing.

The gap is closeable on request, because the emit is public API:

```python
plinta.events.emit_written(obj, changes=..., actor=..., source='nightly_import')
```

Explicit, and it keeps the actor honest rather than inventing one.

### 4.5 A consumer emitting

Three cases, and only one of them is plinta's business.

**An existing signal, for a write plinta did not mediate.** Import the emit
function and call it — no registration, because the vocabulary is already
core's. An EDI importer emitting `object_written` gets audit, notifications and
labels without any of them knowing it exists. A consumer with their own state
machine emits `state_changed` and needs no `contrib.workflow` (§4.8).

**An event of their own** — `order_shipped`, `invoice_paid`. A plain
`django.dispatch.Signal` in their own app, and nothing to do with plinta.
Registration exists so core can be filled by contrib *without importing it*; a
consumer owns both the emitter and the listener, so a module-level signal and a
direct import is both correct and simpler. Nothing in plinta will listen to it.

**A sixth signal in plinta's vocabulary** — no. That is a core change under the
admission test above. Before proposing one, check the first case: a domain event
is usually a write or a state change, and emitting the existing signal is what
buys the listeners.

### 4.6 Batches

A bulk write — an import of 5,000 rows — would emit 5,000 signals and produce 5,000 or more audit rows.

**One signal, plus a batch context.** Not a second `bulk_written` signal, which would make every listener handle two shapes forever.

```python
with events.batch(source='import'):
    ...            # per-row object_written still fires
```

Inside the context a listener may buffer and flush on exit. Audit does one `bulk_create` rather than 5,000 inserts, which is a small change since it already uses `bulk_create`.

The stronger argument is not performance but **notifications**: without batching, one import sends 5,000 emails; with it, the listener coalesces to a single digest. That is a correctness improvement, and it is only possible if listeners can tell that a batch is in progress.

A listener that ignores the context still behaves correctly — just slower.

### 4.7 Failure policy

A listener that raises is logged and swallowed. A failing audit row or a broken notification must never fail a user's save.

The consequence, stated rather than implied: **an audit gap is possible under listener failure.** The alternative — letting an audit failure abort the write — trades a missing row for a failed user action, which is the worse outcome.

Ordering between listeners is undefined and must not be relied upon. Anything slow belongs in a queue the listener owns.

### 4.8 `state_changed` is schema-pure

`from_state` and `to_state` are strings; `metadata` is a JSON-serialisable dict carrying anything workflow-specific — workflow id, transition code, guard results.

Core therefore never references a `Workflow`, `WorkflowState` or `WorkflowTransition` model, and a consumer with their own state machine can emit `state_changed` and get audit and notifications for free.

### 4.9 Permission changes

**A grant or revoke emits `object_written` like any other write** — the target is the `Permission` or group-membership row, the actor is whoever applied it, `source='permission_admin'` (a value that already exists).

No new signal. *Who granted what, to whom, when* is the first question after an incident, and it should not depend on `permission_service` remembering to log it.

### 4.10 What this replaces

Every sideways import in the current tree:

| Was | Becomes |
|---|---|
| `workflow/mixins.py` → `notifications.triggers.fire_workflow_notifications` | emit `state_changed` |
| `workflow/transitions.py:158` → `audit.services.record_transition` | emit `state_changed`; `audit` subscribes |
| `comments/api.py` → `notifications.triggers.fire_comment_notifications` | emit `comment_posted` |
| `blocks/write_pipeline.py` → `notifications.triggers.fire_notifications` | emit `object_written` |
| `blocks/write_pipeline.py` → `audit.services.snapshot_field_values` / `record_changes` | emit `object_writing` / `object_written` |
| `blocks/write_pipeline.py` → `labels.models.LabeledItem` | `labels` listens to `object_written` |
| `actions/apps.py` → `notifications.triggers.register` | **deleted with `actions`** |
| `pages/capabilities.py` → `notifications.triggers._handlers` | capability probe stops consulting the handler registry |
| `actions/models.py` → `workflow.mixins.WorkflowMixin` (base class + 2 FKs + migration dependency) | **not invertible** — `actions` leaves plinta (ADR 0008 (§24)) |
| `blocks/write_pipeline.py` → `workflow.mixins.WorkflowMixin` (`isinstance` in a validation stage) | the stage moves to `contrib.workflow`, which subscribes to `object_writing` |
| `permissions/checks.py`, `permissions/utils.py` → `workflow_state` by name | `WorkflowStateAllowed` and its prefetch move to `contrib.workflow` (§5.4) |


## 5. Layer 3 — permissions



The access engine. Every read and every write passes through it.

**May import:** `utils`, `dates`, `events`.
**Must not know:** what a Block, Page, DataSource, Company, Site or Workflow is.

### 5.0 Old versus new

| | Today | v2 |
|---|---|---|
| **Public surface** | 18 functions in `checks.py` | 3 — `can` / `allowed` / `fields` |
| **Superuser bypass** | hardcoded in **17 sites** | 1, inside the engine |
| **Two-tier rule** | implicit; each caller re-derives it | stated once inside `can()` |
| **Policy attachment** | class attribute on the consumer's model | registered in `policies.py`, autodiscovered |
| **No policy** | falls through to a per-instance loop | model permission decides; startup check reports it |
| **Rules** | 15 concrete, mixed core and domain | 11 in core; domain rules with their contrib app |
| **Reading a model permission in a rule** | impossible — hence `StaffOnly` | `HasPerm` |
| **`is_staff`** | a grant, at 6 sites across 5 apps | means only "may log into `/admin/`" |
| **Publish gate** | `is_staff` | `change_<model>_owner` |
| **Public content editable by** | staff only | `Owner \| InstancePerm \| (Public & HasPerm)` |
| **Field permissions from** | concrete model fields | `DataSourceField` rows |
| **Computed / reverse / property columns** | ungated — the gate returns `True` | minted and enforced |
| **Field gate default** | allow | deny |
| **Actions** | fixed: view / add / change / delete | open set; row actions and capabilities, registered and minted (§5.5) |
| **Organisation rules** | in core | `contrib.organization`, behind generic `FieldInUserSet` |
| **Workflow rule** | in core | `contrib.workflow` |
| **Plinta's own models** | no field permissions possible | registered DataSources, `show_in_api = False` |
| **`checks.py`** | permission checks | Django system checks; logic moves to `engine.py` |
| **Startup validation** | none | missing rule, unminted codename, unregistered annotation |

Unchanged, deliberately: the `Rule` abstraction and its `to_q` / `evaluate` pairing, pk-keyed instance permissions, additive sharing, and the two-tier model itself.

### 5.1 The five questions

This layer answers five things and nothing else:

1. May this user do action A to model M at all?
2. Which rows of M may they do A to — as a queryset filter?
3. May they do A to **this** row?
4. Which fields of M may they see or change?
5. May they do A, where A is not about a model at all — publish, administer?

**The invariant: 2 and 3 must never disagree.** A row that survives the filter must pass the instance check, and vice versa. This is why a `Rule` supplies both a `Q` and a predicate from one declaration — the single best idea in the current design, and it survives unchanged.

### 5.2 Public surface: three functions

```python
can(user, action, target)        # model or instance → bool     (1, 3, 5)
allowed(user, action, queryset)  # → queryset                    (2)
fields(user, action, model)      # → set of field names          (4)
explain(user, action, target)    # → decision trace — diagnostic only (§5.14)
```

Everything in plinta calls only these.

Today `checks.py` exposes **eighteen functions** — `can_view_model`, `can_view_instance`, `can_change_instance`, `can_delete_instance`, `can_act_on_instance`, `filter_viewable_queryset`, `filter_editable_queryset`, `filter_deletable_queryset`, `has_field_permission`, `can_view_field`, `can_change_field`, `get_readable_fields`, `get_editable_fields`, and more. Each caller picks one, which is how the superuser bypass came to be written **seventeen times** across `checks.py` (9), `admin.py` (4), `policy.py` (2) and `sharing.py` (2).

Three functions means the bypass is written once, and the two-tier rule — model permission **and** policy — is stated once inside `can()` rather than rediscovered by every caller.

### 5.3 Policies are registered, not attached

```python
# consumer's policies.py — autodiscovered
register_policy(Instrument, InstrumentPolicy)
```

Today a policy is a class attribute on the model (`permissions = SomePolicy()`), which means touching the consumer's model. Registration keeps their models plain Django and uses the **same pattern** already chosen for queryset modifiers, annotations, components and renderers — one mechanism for everything that plugs in.

**No policy registered → the model permission decides, and all rows are visible.** Row-level control is opt-in; most models never need it. This fails open by design, so it is paired with a startup check (§5.13) listing every DataSource-backed model without a policy — a visible choice, not an oversight.

#### Scoping a parent does not scope its children

A policy governs **one model**. Registering one for `PurchaseOrder` says nothing about `PurchaseOrderLine`, so a line remains visible to anyone holding `view_purchaseorderline` — including the rows of orders the viewer may not see.

This is easy to miss precisely because it looks handled: the parent is scoped, the screen showing parents is correct, and the leak appears only on whatever screen shows the children. In `example/catalog` it was two blocks on the same page — orders narrowed to a manager's own shops, lines from every shop in the chain.

**A related model needs its own policy, usually the same rule through the relation:**

```python
class PurchaseOrderPolicy(PermissionPolicy):
    view = FieldInUserSet("store", user_set=stores_of)

class PurchaseOrderLinePolicy(PermissionPolicy):
    view = FieldInUserSet("order__store", user_set=stores_of)   # through the parent
```

**Nothing infers it**, deliberately. A relation is not evidence of a scope: a `Sale` points at a `Book`, and scoping books by whoever sold one would be absurd. Only the person who wrote the parent's policy knows whether the child inherits it, so the design asks rather than guesses — and the check is what makes the question arrive.

**W001 is what catches it.** It reports every DataSource-backed model without a policy, so a child left unscoped is named at boot rather than found by a viewer. A consumer with a legitimate unscoped model — a shared catalogue — should assert that it is the *only* one reported, which turns the warning into a test.

### 5.4 The rule vocabulary

A `Rule` is a `(to_q, evaluate)` pair, composable with `|`, `&`, `~`.

**Core keeps eleven:** `Owner`, `Public`, `InstancePerm`, `HasPerm`, `FieldEq`, `FieldInUserSet`, `ParentModelPerm`, `UserInM2M`, `GroupOverlap`, `AllowAll`, `Callable`.

The three combinators — `_Or`, `_And`, `_Not` — are unchanged and are not counted here or below.

Today there are **fifteen** concrete rules. Nine are kept as they are, two are deleted, four move to contrib, and two are new:

| Rule | Fate |
|---|---|
| `StaffOnly` | **deleted** — replaced by `HasPerm` (§5.8) |
| `WorkflowStateAllowed` | **→ `contrib.workflow`** — it reads workflow state, which core must not know |
| `UserAccessibleCompany` / `Site` / `BusinessUnit` | **→ `contrib.organization`**, replaced in core by the generic `FieldInUserSet` (ADR 0006 (§24)) |
| `DenyAll` | **deleted** — zero uses; the deny path is the constant `_DENY = Q(pk__in=[])` |
| `HasPerm` | **new** — §5.8 |
| `FieldInUserSet` | **new** — the abstract shape of structural scoping |

`Public` is worth stating plainly, being the most-used rule and the most misread: it admits **a row with no owner**, and says nothing about the user. That is why it never stands alone for editing and always appears paired.

`Callable` is the escape hatch and has exactly **one** use in the codebase, in `organization/policies.py` — a good sign about the vocabulary's completeness. It moves to contrib with its caller.

### 5.5 Actions

`view` / `add` / `change` / `delete` are Django's. Plinta adds `share` and `publish`. `contrib.workflow` adds `transition_<code>`.

So `can(user, 'publish', block)` needs no special case — publishing is an action backed by a permission, not a flag.

#### Row actions and capabilities

Actions come in two kinds, and classifying a new one correctly is the whole difficulty.

**Row actions** — `view`, `change`, `delete`. They have policy rules and filter rows. `allowed(user, 'view', qs)` returns a queryset.

**Capabilities** — `export`, `import`, `publish`, `share`. A model-level yes or no. They do not filter rows; they *compose* with a row action for whatever data they touch.

Export is the clarifying example. It is **not** a row action: there is no set of "exportable rows" distinct from viewable ones. It is the capability `export_<model>` combined with the row filter for `view`. Treating it as a row action would mean writing an `export` rule into every policy that would only ever restate the `view` rule.

**Adding one — three steps, no core change:**

```python
# contrib.export, at ready()
register_action("export", "export", filters_rows=False)
```

1. **Register the action** from the app that provides it. `contrib.export` registers `export`; a future import app registers `import`; `contrib.workflow` registers `transition_<code>`. Registering one of Django's own four is refused — it would shadow a permission Django already mints.
2. **Mint it per model.** `mint_action(model, action)` creates `{action}_{model}`. Plinta cannot add `Meta.permissions` to a consumer's model (§1.2), so nothing else would create it. `datasources` calls this for each registered DataSource, the same split as field permissions (§5.7).
3. **Grant it** like any other permission, and check it with `can(user, 'export', model)` — which takes any action string and needs no change to accept a new one.

**Minting an unregistered action is refused**, or the console offers a permission nothing checks.

`filters_rows` records which kind it is, and **it is enforced**: `allowed(user, 'export', qs)` raises rather than returning a set that looks filtered and is not.

That is not tidiness. A capability has no policy rule, so filtering by one returns every row the *model* permission admits — including rows the user cannot view. An export feature written as `allowed(user, 'export', qs)` would ship data its user has no access to, and the call reads as though it were safe. The two halves are asked separately:

```python
if can(user, "export", Book):                  # the capability
    rows = allowed(user, "view", queryset)     # the rows
```

Django's four are not registered, so nothing here applies to them.

#### Action names are one flat namespace

A consumer may register their own — `approve`, `reconcile`, `settle` — on the
same footing as a contrib package, and refusing would achieve nothing: they own
their models, so `Meta.permissions` gets them the same action without the
registry. All registration adds is that it appears in the console beside
everyone else's.

**A duplicate name raises at startup.** One namespace, no shadowing, as with
placeholders, ranges and queryset modifiers. The consequence to state plainly:
a consumer who registers `approve` and later upgrades into a contrib package
registering the same name gets a **boot failure**, not a warning.

That is the right trade for permissions — silently merging two meanings of
`approve` would grant one app's users the other's access — but it is a surprise
worth warning about, so it belongs in the `start-consumer-app` skill (§25.1)
when that is written.

A capability with no policy rule is tier-1 only: the model permission decides. A policy may still narrow one — `export = HasPerm('…') & ~Public` — but rarely needs to.

**An undeclared action on a policy falls back to the model permission alone.** It does not inherit `view`, and it does not deny. Consistent with §5.3: when tier 2 has nothing to say, tier 1 decides.

Import is the same shape with a different composition: the capability `import_<model>`, plus the write pipeline's ordinary per-row `add` / `change` checks. The capability says you may use the importer; the row checks still decide what it may write.

### 5.6 Two tiers, always both

An action is permitted only when **both** hold:

1. **Model permission** — Django's own `view_x` / `change_x`, held directly or via a group.
2. **Instance policy** — the registered policy admits this object for this user.

Sharing grants tier 2 only. **Sharing never escalates data access**: a recipient still needs the baseline model permission from a role.

### 5.7 Field permissions

Generated from `DataSourceField` rows, not from model fields — a field permission gates a **column**, and a column is a DSF row. Generating for model fields nobody displays produces permissions that can never matter; declared columns that are not model fields — reverse accessors, properties, computed columns — produce none today.

**Fail-open closes.** Today `has_field_permission` returns `True` for anything that is not a concrete field or M2M, so reverse-accessor and `@property` columns are ungated in every install. An undeclared column must deny. Safe because the write pipeline only writes DSF-declared fields.

**Lifecycle — permissions follow the column:**

| Event | Effect |
|---|---|
| DSF created | mint `view_<model>_<field>`; mint `change_…` when `editable` |
| `editable` toggled | mint / remove the change permission |
| `field_name` renamed | **rename the codename on the same `Permission` row**, so grants survive |
| DSF deleted | remove the permissions |
| Computed column | view only; never change |

Deletion is unconditional because a model has exactly one DataSource (§6.1). Rename is where a naive implementation breaks — delete-and-recreate silently drops every grant.

**Plinta's own models are registered as DataSources too** (`show_in_api = False`), so one mechanism covers them: `change_savedview_owner` is what replaces the `is_staff` publish gate. Register only what needs it — the shareables, plus whatever warrants an admin screen — never every model in the project.

#### Who triggers generation

**Permissions owns the function; `datasources` owns the trigger.**

This matters for build order: `permissions` is layer 3 and `datasources` is layer 4, so permissions **cannot** import datasources. The minting function therefore takes a model and field names and never learns what a `DataSourceField` is — which is already the shape of today's `generate_field_permissions_for_model(model, fields=None)`.

```
permissions/fields.py   mint / rename / remove, taking (model, field_names, editable)
datasources             signals on DataSourceField, registered in AppConfig.ready()
```

**No model is imported at module scope, anywhere in plinta.** A package that
does cannot be imported while the app registry is still populating — which is
when a consumer's `AppConfig.ready()` runs — and the `AppRegistryNotReady` it
raises surfaces a long way from its cause. Every package must import before
`django.setup()`, checked by a test that imports each one in a fresh
interpreter.

Today generation is manual — called only from tests and the `rebuild_field_permissions` command — because model-driven generation only needs to change when *code* changes. DSF-driven generation must change when **configuration** changes, so a trigger becomes necessary where none exists.

| Signal | Effect |
|---|---|
| `post_save`, created | mint `view_…`; mint `change_…` when `editable` |
| `post_save`, changed | toggle the change permission as `editable` flips |
| `post_delete` | remove both |

**Rename needs `pre_save`.** Preserving grants requires renaming the codename on the *same* `Permission` row, but `post_save` cannot see the previous `field_name`. So `pre_save` fetches the stored row and stashes the old value on the instance for `post_save` to compare. Without it a rename degrades to delete-and-recreate and silently drops every grant — the failure this rule exists to prevent.

**Bulk paths do not use signals.** `loadconfig` (§16) imports many rows at once, and `bulk_create` does not fire `post_save` at all. Those call `rebuild_field_permissions` once at the end, which is also the idempotent backstop for anything that drifts — matching the existing `rebuild_block_permissions` / `rebuild_page_permissions` / `rebuild_workflow_permissions` family.

**Upgrade note.** Closing fail-open changes behaviour: currently ungated columns vanish unless the migration both mints the permissions and grants them to holders of the model view permission.

### 5.8 `is_staff` is not a permission

**`is_superuser` is the only bypass. Everyone else goes through the permission system, staff included.**

`is_staff` means one thing — this user may log into `/admin/`. Inside `/admin/`, Django gives model-level permissions and no row permissions; that is Django's behaviour and plinta does not fight it. Plinta's own screens enforce policies for staff exactly as for anyone else.

**Six sites treat `is_staff` as a grant** and become permissions: the `StaffOnly` rule itself (`rules.py:122`), public saved views (`components/base.py:295`, `pivots/component.py:301`), public filter sets (`filters/services.py:152,159`) and publishing a report (`reports/views.py:367,414`).

**`HasPerm` — the new rule.** None of today's fifteen reads a model permission, which is exactly why `StaffOnly` existed. It is `StaffOnly` with the flag swapped, user-scoped, so `to_q` is all-or-nothing:

```python
class HasPerm(Rule):
    def __init__(self, codename):          # 'components.change_savedview_owner'
        self.codename = codename

    def to_q(self, user):
        return Q() if user.has_perm(self.codename) else _DENY

    def evaluate(self, user, instance):
        return user.has_perm(self.codename)
```

**Public content stays editable.** The change rule is `Owner | InstancePerm | (Public & Staff)`, and since public means `owner IS NULL` the `Owner` branch can never match a public row — so public saved views, filter sets and reports are today editable *only* by staff. Removing the bypass without a replacement would leave them editable by nobody. It becomes `Owner | InstancePerm | (Public & HasPerm('…change_<model>_owner'))`. Ownership and visibility keep their existing encoding; only the grant moves.

### 5.9 `is_superuser`

**Sees every row** — not merely "holds every model permission". Applied in **one place**, inside `can()` and `allowed()`, replacing seventeen hardcoded sites.

It is not expressed as a `Rule`: a rule would have to be included by every policy, and whoever forgets locks superusers out of that model. The engine decides it.

**Superuser is an infrastructure role, not an application one.** Django grants it everything in `/admin/` regardless, so scoping a superuser inside plinta's screens is theatre that reads as assurance. Tenant administrators are **staff with roles**. A deployment rule, not code.

The saved-view picker narrows to own + public + granted even for a superuser. That is **presentation narrowing, not an access control** — a superuser reaching those rows another way is not a leak, since `/admin/` already shows them. Which gives the general rule:

> Access rules live in policies, always. Presentation narrowing may live at a call site — but it must be labelled as such, so nobody mistakes it for a control or "fixes" it into one.

### 5.10 Instance permissions and sharing

Codename: `{action}_{model_name}_instance_{pk}` — **never by name**, since names are not globally unique and name-keying leaks grants between same-named objects. Renaming an object therefore does not disturb its grants.

Sharing is **additive**: an object is owned *and* shared, and sharing never demotes the owner. Targets are users or groups. `share` / `unshare` / `get_shares` are model-agnostic; a model becomes shareable by registering its lifecycle.

**Three verbs, not one.** They differ in what happens after:

| Verb | Result | After |
|---|---|---|
| **share** | one object, an `InstancePerm` grant per target | the owner keeps editing; everyone sees the change |
| **copy** | a new object owned by the copier | the two diverge |
| **push** | `copy_to` per recipient — each gets their own | N objects, each independently owned and editable |

*"Look at my report"* is share. *"Here is a starting dashboard for your team"* is push. Push needs no new machinery: it is `copy_to` applied to a list, and it requires view on the source plus `add` on the model.

**Copy takes owned children with it** — a Page brings its `PageBlock` and `PageFilter` rows — declared per model rather than implemented per model (§8.10).

### 5.11 The permission console

Moves wholesale into core — it manages Django's own `auth.Permission` and `auth.Group` and owns no models. It **already works without a plinta user model**: `permission_service.py` and `views.py` use `get_user_model()` throughout and reference `CustomUser` nowhere.

Three changes: app grouping (`_is_framework_app` splits on `name.startswith('plinta')`, useless once core and contrib share that prefix — the split becomes core / contrib / project); it lists DSF-declared columns including computed ones; and `user-search` / `group-search` are hardcoded as `/accounts/user-search/` in `comments.js` and `attachments.js`, which are contrib and must not hardcode a core URL.

### 5.12 Module layout

| Module | Holds |
|---|---|
| `rules.py` | the rule vocabulary |
| `policy.py` | `PermissionPolicy` base and the registry |
| `engine.py` | `can` / `allowed` / `fields` — the only public surface |
| `fields.py` | field-permission minting and visibility |
| `codenames.py` | every naming convention, in one place |
| `sharing.py` | share / unshare / get_shares |
| `console/` | the permission UI |
| `checks.py` | **Django system checks** |

Note the rename: today `checks.py` means "permission checks", colliding with Django's own `checks` framework. Permission logic becomes `engine.py`; `checks.py` becomes what Django expects.

### 5.13 Startup validation

Because a missing policy fails open (§5.3), misconfiguration must be visible at boot rather than in production.

**Each check belongs to the layer that can see what it validates.** Two of the three need a DataSource, which `permissions` (layer 3) cannot import — the same split §3.6 makes for unresolved placeholders.

| Check | Severity | Owned by |
|---|---|---|
| a `HasPerm` naming an **unminted codename** | error | **`permissions`** — it has the policy registry and the permission table |
| a DataSource-backed model with **no registered policy** | informational — it is a legitimate choice | `datasources` |
| a `DataSourceField` naming an **unregistered annotation** | error | `datasources` |

A missing `HasPerm` codename is not a silent no-op: the rule denies, so a policy written to admit rows refuses all of them, and the trace in `explain` says only that the branch failed. The check names the model, the action and the codename.

**A check must survive an unmigrated database.** Checks run during `migrate`, before the tables exist, so one that queries rows returns nothing rather than raising — failing there would block the migration that fixes it.

### 5.14 `explain(user, action, target)`

A fourth function, and the one that pays for itself in operations.

```python
explain(user, action, target)   # → a decision trace
```

The most common question in any permission system is *why can this user not see this row?*, and today the only answer is to read the policy and reason by hand.

A policy is a tree of composable `Rule` objects, so the engine can walk it and report which tier failed — model permission or policy — and which branch of the tree denied: `Owner` no, `Public` no, `InstancePerm` no, therefore denied.

Cheap, because it exposes structure that already exists rather than building new machinery. The console answers "who holds this permission"; this is the inverse, and the harder half.

It is a **diagnostic**, not a decision path: `can()` must never call it, so an expensive or partial trace can never change an answer.

### 5.15 Grant safety

**A non-superuser may only grant permissions they themselves hold.**

Without this invariant, anyone able to administer permissions can promote themselves. v1's `apply_permission_changes` took an `actor` argument and used it **only for the audit row** — so the trail recorded who escalated, and nothing stopped them. The defence is one check in the apply path, and it closes the class rather than the instance.

| | |
|---|---|
| Grant | only what the granter holds, directly or through a group |
| Grant to a **group** | the same rule — a group grant reaches every member, so it cannot be looser |
| Revoke | **unrestricted**; removing access cannot escalate anyone |
| Join a group | bounded by what the group **carries**, never by its name |
| Superuser | may grant anything |

**All or nothing.** A grant naming several permissions applies none of them if one is refused. A partial grant leaves the caller unable to tell what happened, and re-running it compounds the difference.

**The group rule is about contents, not names.** A group called *Read only* that carries `delete_book` is exactly the case a name-based rule misses, so joining one requires holding everything in it.

This module enforces escalation only. Whether someone may administer permissions at all is an ordinary `can(user, "change", Permission)` question, asked by whatever exposes the screen.

### 5.16 Anonymous users

Unauthenticated users are denied before any rule runs.

Already the behaviour (`policy.py:61,67`) but nowhere stated, which leaves it looking undefined — and "public means everyone" invites the question. It does not include logged-out visitors. A public object is visible to every *authenticated* user holding the baseline model permission.

### 5.17 The chunked fallback loop is deleted

`_filter_queryset_by_action` walks a queryset in chunks of 2,000, calling the instance check per row. It runs when a model has **no policy** — and in that case every row passes anyway, because the fallback is the model permission.

So an unpolicied model with 50,000 rows iterates all of them to conclude "all of them".

§5.3 answers that case directly: no policy means the model permission decides and rows are not filtered. And since every `Rule` implements `to_q`, there is no "policy exists but cannot produce a `Q`" case either. The loop has nothing left to do, and a latent performance cliff goes with it.

### 5.18 Deny rules are rejected

Explicit deny that overrides allow is the most-requested feature in permission systems and the one that ruins them: it forces precedence rules, makes every decision order-dependent, and turns `explain()` from a trace into an argument.

`~Rule` already exists as a combinator for composing a negative *inside* a policy, which covers the honest cases.

If a role sees too much, the answer is a narrower grant, not a subtractive one.


## 6. Layer 4 — datasources



The model registry. Makes a Django model available to plinta and declares how its columns behave.

**May import:** `utils`, `dates`, `events`, `permissions`.
**Must not know:** what a Block, Component or Page is.

### 6.1 Models

| Model | Fields |
|---|---|
| `DataSource` | `name`, `label`, `description`, `content_type` (**unique**), `is_active`, `show_in_api`, timestamps |
| `DataSourceField` | `data_source`, `field_name`, `label`, `order` + the 16 options below |

Registration is **data** — a row, created in the UI or by a command. Never a decorator. Adding a DataSource is configuration; adding the model behind it is code.

**One DataSource per model.** `content_type` is unique. Today only `name` is unique, so several DataSources may point at one model; that is a change.

A DataSource says *this model is available to plinta*, which is a fact about the model, not a view of it. Per-screen variation already belongs a layer up: a `Block` chooses which columns to show, and `base_filter` and `queryset_modifier` narrow the rows. A second DataSource over the same model duplicates what a second Block already does.

It also makes field permissions exact. The codename `view_<model>_<field>` names a model and a field but not a DataSource, so with several DataSources per model one permission is shared between them — and deleting a column from one screen would revoke it on another, destroying the grants. Uniqueness removes that class of bug rather than guarding against it.

Migration: existing installs with two DataSources on one model must merge them, keeping the union of columns.

### 6.1a `show_in_api`

**Default `False`.** A DataSource is exposed as a public API resource only when this is set.

**This reverses the earlier decision** (§15, ADR 0007 (§24)) that registration alone publishes a resource and no flag is needed. That decision was argued on security grounds and those still hold: every API entry point is permission-filtered, so an unentitled caller learns nothing whether the flag exists or not.

What changed is **curation**. Plinta's own models are registered as DataSources so that DSF-driven field permissions cover them (§5.7) — which would otherwise put `SavedView`, `PageBlock`, `EmailQueue` and their kin into the public API as stable, versioned resources. That is materially more noise than the handful being weighed when the flag was rejected.

So the flag returns for a different reason than the one rejected. It is **surface curation, not access control** — permissions remain the only gate on what a caller may read.

Per-field API flags stay rejected: field permissions already answer that question, and a second mechanism would drift.

### 6.2 `DataSourceField` options

| Option | Used | Decision | Note |
|---|---|---|---|
| `sorter` | 278 | keep | string / number / date |
| `filter_lookup` | 279 | keep | exact 272, in 5, range 2 |
| `editor_widget` | 279 | keep + **rename** | → `picker_mode`; values `auto` / `list` / `search` |
| `visible` | 275 | keep | |
| `header_filter` | 200 | keep | input 127, select 52 |
| `format` | 45 | keep + **narrow** | `date`, `datetime`, `textarea`, `html` only — see §6.8 |
| `editable` | 13 | keep | |
| `filterable` | 9 | keep | |
| `filter_widget` | 9 | keep | multiselect, daterange |
| `filter_display_format` | 6 | keep | `{workflow_state__name}` templating |
| `width` | 0 | keep | Tabulator passthrough; default suffices |
| `decimals` | — | **add** | new — see §6.8 |
| `thousands_separator` | — | **add** | new — see §6.8 |
| `prefix` | — | **add** | drawn before the value — see §6.8 |
| `suffix` | — | **add** | drawn after — see §6.8 |
| `is_fiscal_year` | 0 | **drop** | ERP schema convention → ADR 0006 (§24) |
| `is_month` | 0 | **drop** | as above |
| `recompute_siblings` | 0 | **drop flag** | invert default: always return the updated row |
| `edit_modal_block` | 0 | **drop** | edits another block's records from an FK cell — see §6.7 |
| `editor_queryset_filter` | 0 | **drop** | arbitrary ORM filter in config, unenforced on write — see §6.7 |

### 6.3 Services

Three functions, all taking the requesting user:

- `get_queryset(datasource, user)` → rows the user may see, row-policy filtered
- `get_available_fields(datasource, user)` → fields the user may see, field-permission filtered
- `search_q(datasource, user, q)` → a `Q` matching text across the fields that user may search

`search_q` returns a **`Q`, not a queryset**, so callers can compose it — a table header filter ANDs it with existing filters; a picker applies it alone.

`user` is **required**. There is no unfiltered path and no system user.

Today the signature is `get_queryset(data_source, user=None)` with `if user:` inside, so omitting the argument silently returns every row. All twelve callers pass a user, so the unfiltered path has no consumer — it is only a footgun. Omitting it must be a `TypeError` at the call site, not an empty result and not a leak.

Background work runs **as a real user**: `ScheduledReport.run_as_user` already does this. A superuser sees everything through the normal path.

Everything above this layer — blocks, pages, export, the API — inherits its narrowing from here and cannot widen it.

### 6.4 Queryset modifiers

Named, registered callables that narrow a queryset. Registered, never resolved from a dotted path in config, so configuration cannot name arbitrary importable code. May narrow; must not widen. Consumers declare theirs in a `queryset_modifiers` module.

### 6.5 Prefetch derivation

Deriving `select_related` / `prefetch_related` from the requested columns belongs **here**, not in a component.

The inputs are both this layer's: the column list comes from `DataSourceField`, the queryset from `get_queryset`. A component contributes nothing to the decision.

Today it lives in `components/tables/component.py::_build_prefetch`, which walks each column — traversed paths (`company__code`) to the deepest relation segment for `select_related`, reverse accessors for `prefetch_related`, HTML-formatted FK columns for `select_related`. The logic is sound; only its location is wrong.

The cost of that location, measured:

| Component | Query optimisation today |
|---|---|
| table | derived automatically |
| gantt | 6 hand-rolled calls |
| kanban | 5 hand-rolled |
| pivot | 3 hand-rolled |
| chart, kpi, gauge, repeater, details-card | **none** |

All nine call the same `get_queryset(data_source, user)`. Four re-implement a fraction of the derivation; five N+1 on any relation column. Moving it down fixes five components, deletes four partial copies, and means a tenth component gets it without knowing it exists.

**No config option.** Declarative hints would duplicate what derivation computes. The one case derivation cannot see — a custom field renderer touching a relation no column names — is handled by the renderer **declaring what it needs joined** as part of its registration, which also removes the duck-typed `table_select_related()` model protocol.

**The derived path is the default, not an opt-in.** `get_queryset(ds, user)` derives from every column the user may view; a caller narrows by passing `columns=[…]`, or opts out with `columns=[]`. Leaving derivation to the caller would have moved the defect rather than fixed it — five of v1's nine components did not call it, and a tenth would have been one more chance to forget.

**Verified**, on three rows with a relation column: four queries reading it without derivation, one with. A many-to-many costs two rather than one per row.

### 6.6 Search

Search belongs here, for the same reason as prefetch derivation: it needs the queryset, the field metadata, and the per-user field permissions, and all three are this layer's.

Today it lives in `datasources/api.py::_do_object_search`, an endpoint helper, and the table's header filters implement their own `icontains` separately.

**Two default fixes — decided.**

1. **Search only fields the user may see.** Intersect the searched columns with `get_available_fields(datasource, user)`. Rows are already permission-filtered, but *which columns are searched* is not — so a user who cannot see a column can still search it and learn from the result set whether a record matches. It leaks presence rather than content, but it is an oracle and it is invisible. The intersection costs nothing; the layer already computes the list.
2. **Default to visible columns, not every text field.** The current fallback ORs `icontains` across every `CharField` and `TextField` on the model — its own docstring calls it "broad but noisy". Matching on a column the user cannot see produces results they cannot explain.

Performance matters here because one caller is not user-gated: table header filters wait for Enter, but the **inline FK editor's autocomplete hits the endpoint per keystroke** (`table.js:116`). `icontains` is a leading-wildcard `LIKE`, which no index serves, OR'd across every text column.

**Targeted search stops being a side effect.** Today a field gets sensible search only if it has a `filter_display_format`, whose paths are reused as the search paths — good reasoning, but it means search quality is a by-product of label configuration. Set on 6 of 279 fields; the other 273 take the broad path. `searchable` (§22.2) expresses the intent directly, with the display format's paths as the fallback when nothing is declared.

**Consumers.** The FK picker, the inline FK editor, table header filters, the public API's `?search=`, and any future global search all call `search_q`. The two fixes above then apply everywhere at once rather than in four places.

Not to be confused with `datasources/api.py::fields_search`, which searches `DataSourceField` rows by label for the config UI — plinta's own metadata, not a consumer's data. Different concern, same word; it stays where it is.

### 6.7 Decisions

| Item | Decision |
|---|---|
| Field paths traversing relations (`company__code`) | keep |
| Reverse relations and properties as read-only columns | keep |
| FK object-search endpoint | keep |
| — its `hasattr(model, 'site')` label decoration | **drop** — hardcoded org knowledge in core |
| Fiscal auto-detection by column name suffix | **drop** |
| `edit_modal_block` — pencil on an FK cell opens another block's edit modal | **drop** |
| `editor_queryset_filter` — ORM filter dict narrowing an FK picker's choices | **drop** |

**Rule: a block edits records of its own DataSource, never another's.** Each table is responsible for its own data. Editing a related record through a cell also means checking a second model's permissions in a path that is not visibly about that model — a trap worth designing out rather than guarding.

`editor_queryset_filter` narrows *which value you may pick*, not what you may edit, so it is legitimate in principle. It goes because it is an arbitrary ORM filter dict living in configuration — the same thing rejected for queryset modifiers, which must be registered names — and because it is applied on three read paths and **nowhere on write**, so it constrains the dropdown but not the save. If picker-narrowing is wanted later it returns as a *registered named filter*.

**`picker_mode` values.** `auto` · `list` · `search`. `auto` is the default and picks `list` under 100 rows, `search` above it.

### 6.8 Additions

**`decimals` and `thousands_separator` on `DataSourceField`.** Decided.

Precision is currently hardcoded in `renderers/table/html.py` — currency 2, percent 1, number **0** — so a field cannot ask for four decimals. A finance consumer hits that ceiling on its first price column.

Those per-format defaults do not survive: `decimals` is nullable and unset means the value's own precision (§7.1).

This is deduplication more than a new feature. The same "2 decimals" is declared twice today: implicitly by `format='currency'`, and again per-pivot in `PivotBlockConfig.formats`, which is a `list[dict[str, Any]]` carrying **Flexmonster's own format objects** unvalidated inside `Block.config`.

Declared once on the field, every renderer honours it — the rule §7.1 already states for dates ("a date renders identically in HTML and in a spreadsheet because both call the same helper"). It also pulls vendor-shaped structure out of block config: a pivot may keep vendor config for vendor concerns, but formatting is universal.

**`prefix` and `suffix` on `DataSourceField`.** Decided. Free text drawn around the value — a symbol, a unit, anything. Generic on purpose: `$`, `kg`, `ms`, `°C` and `%` become one mechanism, and core never learns what any of them mean.

**`format` loses `currency`, `percent` and `number`.** Decided. Once precision is a knob and the symbol is a knob, those three members do the same thing as each other and nothing the knobs do not already say. A configurer describing money sets `prefix='$'` and `decimals=2`; a percentage is `suffix='%'`. This is the shape a pivot library already uses — a bag of display options, not a taxonomy of formats — and it is why `PivotBlockConfig.formats` could carry vendor format objects at all.

Numeric treatment follows from the knobs: a column declaring `decimals` or `thousands_separator` has its value formatted as a number even when it arrives as a string, so nothing needs to say it twice.

What survives are the four choices no knob can express: `date` and `datetime` (a datetime column showing the day only), and `textarea` and `html`, which the HTML renderer reads.

**No `currency` field.** It was written and removed: nothing in core would have read it, and a currency code is a domain noun, which §2.2's noun test places in contrib. A consumer needing per-column denomination — for conversion, or a rate table — declares it in `contrib.organization` with an FK to the `DataSourceField`, the way every contrib app hangs data off core.

### 6.9 Checks this layer registers

Two, both from §5.13, which could not live in `permissions` because that layer
cannot import a DataSource.

**A DataSource-backed model with no registered policy** — informational, not an
error. Row-level control is opt-in and most models never need it (§5.3), but
the absence fails open, so it is reported rather than assumed.

**A `DataSourceField` naming an unregistered annotation** — an error. The column
would render as nothing with no indication why, since the queryset simply never
gains the annotation.

Both read rows, so both return nothing on a `DatabaseError` (§20.3).

**This layer also owns two minting triggers**, for the same reason: `permissions` cannot enumerate DataSources.

| On | Call |
|---|---|
| a `DataSourceField` saved, renamed or deleted | `sync_field` / `rename_field` / `remove_field` (§5.7) |
| a DataSource registered, and any action registered later | `mint_for(model)` (§5.5) |

### 6.10 Computed columns

**Registered ORM annotations. Argument-free. Nothing else.**

```python
# consumer's annotations.py — autodiscovered
@register_annotation('order_total', output_field=DecimalField())
def order_total():
    return F('qty') * F('price')
```

A `DataSourceField` whose `field_name` matches a registered annotation gets it applied. It then inherits label, `format`, `decimals`, sorter, filter widget, ordering and permissions — no new model, no new config surface.

Because the annotation is SQL, the column **sorts and filters in the database**. A `@property` cannot: it is Python-side and invisible to the ORM.

**Everything Django can express is available** — `Subquery`/`OuterRef` for "latest price", `Exists` for "has attachments", `Case/When` for buckets, `Concat` for names, `Window` for ranking. The tier boundary is about where the expression is *authored*, not which expressions exist.

**Rejected: expressions in config** (`"qty * price"`). Strictly *less* capable, not more — a config parser would implement a small arithmetic subset and never reach `Subquery`. It also puts user-authored code in runtime-editable data, requiring a sandboxed evaluator, and it grows into a spreadsheet engine one request at a time. It crosses the line in §1: consumers configure the surface, developers define the schema.

**Rejected: arguments from config** (`{"annotation": "count_of", "args": {...}}`). Every argument is a path from data into an ORM call, and therefore a validation surface. Argument-free means the developer wrote the relation, knew the model, and owns the consequence — Django raises if it is wrong. The cost is one registration per computed column per model; that is accepted.

**What plinta still owns:**

- **Name resolution.** Config stores a name; an unregistered name is rejected at save, as with `queryset_modifier`. Without it a typo crashes every render of the page.
- **`output_field`** at registration — needed to choose a sorter and a filter widget.
- **A field permission of its own** — `view_<model>_<order_total>`, generated and granted like any other column's. See §5.

Correctness of the expression is the consumer's; plinta does not police it.

**Where it is applied.** `get_queryset` annotates whichever of its columns are registered, before deriving joins — so a computed column arrives sorted and filtered like any other, and a caller does nothing special. Prefetch derivation skips it: an annotation is not a relation path and there is nothing to join.

**Documented gotcha.** Two join-based aggregates in one queryset multiply each other's rows — `Count('line_items')` beside `Count('shipments')` returns wrong numbers *and* breaks pagination, because the row count changes. Use `distinct=True` or `Subquery`-based aggregates. This is guidance, not validation, and it belongs beside the registration example: it looks like a plinta bug and costs a day to find.

**Read-only, always.**

---

## 7. Layers 5–6 — renderers and components



Build layers 5 and 6. Two contracts, in dependency order — `components` may import `renderers`; the reverse is forbidden.

### 7.1 Renderers — the output contract

**May import:** `utils`, `dates`, `permissions`, `datasources`.
**Must not know:** what a Block, Page or Component is, or which formats are installed. `components` imports this layer for the shared format helpers; the reverse must never happen.

```python
render(rows, fields, config, user) -> output
```

**A renderer never queries.** Rows arrive already filtered by row policy, fields already filtered by field permission. That is what makes a renderer structurally incapable of widening access — it cannot fetch what it was not given.

Registration mirrors components: `register_renderer(format)`, called from the owning app's `AppConfig.ready()`.

**The registry substitutes rather than fails.** `get_renderer(format)` returns the registered renderer, or the HTML renderer when that format is not installed — the `get_current_site()` / `RequestSite` pattern from §2.5. So a caller never asks whether `contrib.export` is installed:

```python
renderer = renderers.get('xlsx')     # export installed  -> the xlsx renderer
                                     # not installed     -> the html renderer
```

A report defined against `xlsx` still runs without `export`; it renders to screen. That is what makes `enhances` a real relationship rather than a guard that hides a button, and it is why no package needs to import `contrib.export` to produce a file.

A format the caller **explicitly** requests over HTTP and which is not installed is a 404, not a silent HTML response — substitution is for internal callers, not for content negotiation.

**Core ships HTML.** Excel, PDF and email ship with `contrib.export`, for dependency weight rather than size: `openpyxl`, `pandas` and `weasyprint` — the last needing GTK native libraries — are the heaviest things in the project and none is required to render a screen.

**Escaping happens in the cell, not in whoever inserts it.** A field renderer's output and an `html` column are markup by intent and pass through; everything else is escaped where it is drawn, so there is no way to use `cell()` and get it wrong. A column **label** is escaped too — configuration is written by people.

**Shared format helpers live here.** Dates, numbers, currency, booleans and related objects format identically in HTML, a spreadsheet and an email because all three call the same helper. This is where `decimals` and `thousands_separator` (§6.8) land — declared once on the field, honoured by every format.

Formatting is driven entirely by what the column declares — `decimals`, `thousands_separator`, `prefix`, `suffix` — and core imposes nothing (§6.8). Three decisions the helpers settle once:

**`percent` treats the stored value as the percentage.** 15 renders as "15.0%". Multiplying by a hundred here would make a renderer change the meaning of the data; a column storing a 0–1 fraction declares an annotation that multiplies, where the arithmetic is visible.

**Numbers round, they do not truncate.** Django's `number_format` truncates to `decimal_pos`, so 1.999 in a currency column would show as 1.99. The value is quantized before formatting.

**A format imposes no precision; an unset column keeps the value's own.** `decimals` is nullable, and NULL means *leave the number alone* — 1234.5 shows as 1234.5. There is no per-format default table: v1 hardcoded currency 2, percent 1 and number **0**, which is where §6.8's ceiling came from, and a default of zero rounds a price of 5.49 to 5 while looking entirely correct. A ragged column asks to be fixed; a wrong number does not. `decimals=0` is a real instruction, distinct from unset.

**Dates go through Django's format machinery, so the active locale decides.** Django 6 localises unconditionally; `DATE_FORMAT` is reached only when the locale module lacks it. That choice is Django's and plinta does not second-guess it.

**A column draws its own affixes, and core does not convert.** `prefix` and `suffix` (§6.8) go around the formatted value, whatever its type. One rule governs them:

> Exactly what the column declared, in the order it declared it. No format contributes a sign of its own, and nothing is rearranged around a minus.

So a `percent` column draws `%` because it declared `suffix='%'`, not because the format did. The only rule left is that an **empty cell takes no affix**, or a blank currency column renders as a lone symbol.

**Negative numbers are not core's convention to pick.** Accounting writes `(5.00)`, some styles `-$5.00`, others `$-5.00`. Any choice made here is wrong for someone, so none is made: a column wanting one registers a field renderer (§7.8), which is also where symbols and conversion live.

A setting could not express a screen showing dollars and euros side by side, which is the ordinary case for the consumer this exists for.

`components` imports this layer for those helpers. That is the only direction allowed.

### 7.2 Components — config in, HTML out

**May import:** `utils`, `dates`, `events`, `permissions`, `datasources`, `renderers`.
**Must not know:** that saved views exist, that a Block or Page exists, or which other components are installed.

```python
render(config, user, **context) -> str
```

The config arriving is **already final**. A component does not fetch its own configuration, does not merge a personalisation delta, and does not know whose view it is rendering.

The merge happens one layer up, in `blocks`, which holds `SavedView` (§8.1). The **contract is unchanged** by that: a component is handed a resolved config either way, and never learns a saved view was involved.

Each component declares a pydantic config schema with `extra='forbid'`, so a typo is rejected at save time rather than ignored at render time. Strict validation is only possible because exactly one shape arrives — not "the block config, unless a view overrode it".

**Core ships `table_plinta` and nothing else** (ADR 0005 (§24)). Every other component registers through the same door a third party would use, so the contract is dogfooded rather than asserted.

A block referencing an unregistered component type renders as an **empty slot** — a normal state, not an error, mirroring how a page already degrades a block the viewer may not see. The registry offers both lookups: `find` returns None, which is that path, and `get` raises for a caller that already knows the type is installed.

**A column choice is config, and it narrows.** `columns` is on the base schema, because it is where a saved view's column choice arrives once `blocks` has merged it (§8.2) — a saved view's editor *is* column-visibility UI (§14.4).

Three sources, three jobs: `DataSourceField.visible` is the DataSource's default order, field permission is the **ceiling**, and the merged config is what this viewer chose out of what they may see. So the config narrows and reorders and can never widen: a name the viewer has no permission for is dropped rather than honoured, the same fail-closed rule an undeclared column already follows (§5.7). Otherwise personalisation would be a permission bypass — save a view naming a revoked column and get it back.

**`get_data` is on the base class**, so it calls `get_available_fields`, collects the joins the columns' field renderers declared (§7.8), and passes both to `get_queryset`. A component written tomorrow gets prefetch derivation and computed columns without knowing either exists; one that needs to narrow further overrides it and calls `super()` first — which is how `table_plinta` applies its `sort`.

### 7.3 Two rendering modes

Every component implements `get_data()`. The mode decides *when* it is called:

| Mode | Behaviour |
|---|---|
| `inline` | `get_data()` runs during page render; rows are embedded in the HTML |
| `fetch` | the page returns a mount point; the client requests the data separately |

**The component declares a default; a block may override it.** The default follows from the widget's interaction model and is right nearly always; the override covers genuine exceptions — a five-row related grid on a detail page, or a chart with 50,000 points that should not bloat the page.

**Within what the component can draw.** A component also declares `supported_modes`, and a block asking for one outside it is refused when it is saved. Core's `table_plinta` supports `inline` only: it is server-rendered and has no client adapter, so a `fetch` block would render nothing and say nothing about why. `table_tabulator` supports both — `inline` is Tabulator's `paginationMode: 'local'`, which is what a five-row grid wants.

**Changing how a table behaves is changing the component, not the mode.** Installing `contrib.components.table_tabulator` does not make `table_plinta` interactive; a block's `component_type` moves from one to the other, and the new component's default mode comes with it. Mode says *when the data arrives*, not *which widget draws it* — and since the two components declare different config schemas, the switch is validated at save like any other config change.

| Component | Default | Why |
|---|---|---|
| `table_tabulator`, `kanban_plinta`, `gantt_jsgantt`, the pivots | **fetch** | the client sorts, filters and pages; a 10,000-row grid cannot be inlined |
| `chart_plotly`, `kpi_plinta`, `gauge_plotly` | **inline** | a finished data blob, or a single number; no client-side manipulation |
| `table_plinta` | **inline** | server-rendered; sorting and paging are links, not a client (§11.2) |
| `details_card_plinta`, `text_plinta`, `alert_plinta`, `repeater_plinta`, capability sections | **inline** | display only |

**Three defaults change.** `chart`, `kpi` and `gauge` are `AJAX = True` today, so a dashboard with eight KPIs makes eight extra round trips to deliver eight numbers. The recorded reason was not payload size — `kpis/component.py:59` says *"gating runs in the AJAX endpoint, not here"* — so the mode was chosen to put the permission check in one place. Under §5 that reason is gone: `can()` and `allowed()` are called by the data path wherever it runs.

**The modes align with dataset size, and that is not a coincidence.** Inline implies the client sorts and filters locally, which is only viable for small results — which is exactly when inline is chosen. Fetch implies the server does that work, which is required for large ones. For Tabulator this is the difference between `paginationMode: 'local'` and `'remote'`; an inline table is a differently configured widget, not the same widget pre-loaded.

**Inline data has a defined home in the page** — a `<script type="application/json">` beside the mount, with a predictable id. Fixed here so adapters do not each invent one.

#### Where the data endpoint lives

`fetch` mode implies an endpoint. It is **private transport**: a plain Django view returning JSON, block-scoped, versionless, with no stability promise.

Not ninja. §15 keeps ninja for the public API alone, and this is neither a public resource nor an HTML fragment — but it shares the fragments' properties: it is plinta's own frontend talking to plinta, and it changes whenever the UI does.

#### It is not the public API, and must not become it

Tempting, since both return rows over a DataSource.

**The reason is not that block config is editable.** `DataSourceField` rows are edited in a browser too (§12.1), and the public API is generated from them (§15.1), so both surfaces take their columns from configuration a user can change. That distinction does not separate them.

**The reason is that the widget feed's shape depends on who is asking.** A saved view is a per-viewer delta over the block's config, so two people requesting the same URL get different columns. No versioned contract can promise that, and no OpenAPI schema can describe it. The public API's shape varies with configuration; the widget feed's varies with the *viewer*, and that is a different kind of thing.

| | Widget feed | Public API |
|---|---|---|
| Scoped to | a **Block** | a **DataSource** |
| Shaped by | block config **and the viewer's saved view** | the DataSource's fields |
| Same URL, two users | **different columns** | the same columns |
| Cardinality | many blocks per model, rearranged daily | one DataSource per model (§6.1) |
| Versioned | no | yes |

Unifying them would put a per-viewer response behind a version guarantee, and leak block identity into the public contract — `/api/v1/data/instruments/?block=instruments-table`.

**What they do share is underneath**: both go through `get_queryset`, `get_available_fields` and `search_q` (§6.3), so both inherit the same row filtering, the same field permissions and the same search behaviour. That is the part that should be common, and it already is — the layer below both.

Permission gating therefore needs no special case in either: whichever path is taken, the narrowing happened in `datasources`.

#### Getting the screen rather than the model

A caller may legitimately want a table exactly as it appears — the block's columns, in order, with visibility and the viewer's saved view applied. That does **not** come from `/api/v1/data/{ds}/`.

Not because block-shaped output is dangerous, but because the two URLs name **different things**. `/api/v1/data/instruments/` is *the Instrument resource*. Block-shaped output is *this screen*. Different identity, different endpoint.

**It comes from the export path.** The renderer registry is already keyed by `(component_type, output_format)`, and the export path already assembles an **effective view** before rendering. So a registered `('table', 'json')` renderer gives block-shaped, view-applied JSON through machinery that exists:

```
/blocks/<name>/export/?format=json
```

No new endpoint, no new concept — one registration.

So there are three surfaces, and each answers a different question:

| Surface | Answers | Shape follows |
|---|---|---|
| `/api/v1/data/{ds}/` | *what is in this model?* | the DataSource |
| the widget feed | *what should this widget draw now?* | the block, live |
| `/blocks/<name>/export/` | *give me this screen, in a format* | the block |

**The contract for the last two: shape follows the block.** Edit a block's columns and the payload changes. That is the operator's call and the operator's consequence, exactly like any other configuration change — plinta states the rule and does not attempt to prevent it.

#### Applying a saved filter

A `FilterSet` is **values, not shape**. Applying one narrows rows without altering the resource contract, so it belongs on the public API — `/api/v1/data/{ds}/?filter=…` already covers it.

**The caller expands it.** `FilterSet` is already registered as a DataSource (§5.7, which is how `change_filterset_owner` is minted); publishing it is one flag, `show_in_api = True`. Two calls:

```http
GET /api/v1/data/filterset/?filter={"name": "My Tech Longs"}
→ {"id": 42, "data_source": 7, "values": {"sector": "Tech", "status": "open"}}

GET /api/v1/data/instruments/?filter={"sector": "Tech", "status": "open"}
```

Three things come free. **Permissions**: reading a FilterSet needs `view_filterset` plus its policy — `Owner | Public | InstancePerm` — so a caller sees their own, public ones, and ones shared with them, with no code. **Placeholders**: stored values containing `__CURRENT_QUARTER__` pass through verbatim and resolve server-side on the way in (§3.6), so the macro survives client-side expansion. **Inspectability**: the caller can modify a value before applying it.

The cost is a second round trip.

##### Rejected: a query-parameter registry

`?filterset=42` resolved server-side would mean `contrib.api` reaching into `pages` for a `FilterSet`, which is legal — contrib may import any core layer — but would still add a fourth registry.

Rejected because the design already carries four registries — annotations (§6.10), queryset modifiers (§6.4), placeholders (§3.6) and date ranges (§3.6) — and a fifth must earn its place. One boolean on one model achieves the same thing.

**The test before adding a registry:** if a proposed registry shares an input shape and an output shape with an existing one, it is the same registry under another name. The four differ genuinely — the query-parameter one is the only one the *caller* drives rather than configuration — but "genuinely different" is not the same as "worth its weight."

Still available if `?filterset=` proves to be repeatedly asked for. By then it would be a known want rather than a guess.

### 7.4 The front end: one client, N adapters

Four widget files today each re-implement the same plumbing: `table.js` (628 lines), `kanban.js` (392), `pivot.js` (248), `gantt.js` (188) — between them 9 `fetch` calls, 14 catch blocks, 4 loading indicators and 7 CSRF handlings, for one behaviour.

Two kinds of work are mixed together in each:

| Plumbing — identical everywhere | Vendor glue — different each time |
|---|---|
| find the mount, read its config | build Tabulator column definitions |
| build request params: page, size, sort, filters, view, tab | assemble Plotly traces and layout |
| fetch; attach CSRF for writes | build the jsGantt task array |
| loading, empty and error states | assemble the Flexmonster report |
| re-fetch when a page filter changes | wire cell editors |
| preserve scroll across refresh | |

**The client is the left column, written once. An adapter is the right column, one per component type.** Core's own `table_plinta` needs neither, being server-rendered (§11.2); the client exists for the components that fetch, and ships in core so contrib does not each write one.

```js
registerAdapter('table', TableAdapter);

// the client, per mount: read config → resolve mode → hand the adapter a loader
adapter.mount(el, { config, columns, data, load });
```

**The client owns `load(params) → Promise<data>`** — the URL, the parameter names, the CSRF token, error handling, the loading state.
**The adapter owns *when* to call it** — once at mount for a chart; on every page, sort and filter change for a table.

This is what makes remote pagination work without the client owning timing: Tabulator's `ajaxRequestFunc` delegates to `load()`, so Tabulator decides *when* page 3 is needed while the client still decides *how* it is requested. Plotly's adapter calls `load()` once and never again. Both get identical parameter building and error handling.

**An adapter is per component type, not per vendor.** `chart_plotly` and `gauge_plotly` share a vendor and still need different glue — a gauge is an indicator trace, a chart is line/bar/scatter. Where two adapters genuinely share vendor logic, a shared helper serves them: `plotly-theme.js` is already exactly this and survives unchanged.

**Adapters ship with their components.** Core carries the client and nothing else — `table_plinta` is server-rendered and needs no adapter; `contrib.components.chart_plotly` carries its adapter and Plotly. Same rule as vendor assets (§17) and ADR 0005 (§24).

### 7.5 Module format: ES modules

**Settled — and already the practice.** `base.html:119` loads `core.js` with `type="module"`, and 17 of the JS files already use `import` / `export`.

The reason to keep it is not modernity but **legibility**: a module's first lines state exactly what it needs. Globals hide the dependency graph, which is the front-end version of the problem this rebuild exists to fix — `permissions` importing nine apps with no readable direction would simply be invisible in JS.

Two known limits, both solved natively when they bite:

- **bare specifiers** — `import 'tabulator'` needs an **import map**, one tag in the base template
- **hashed static storage** — Django rewrites `url()` in CSS but **not `import` statements in JS**, so relative imports break under `ManifestStaticFilesStorage`. An import map generated by a template tag fixes this too. Neither the deployment docs nor the example project set a storage backend, so it has not bitten; a consumer enabling hashing would hit it, and it belongs in the deployment notes.

**Changing later is cheap, and this choice preserves the most options:**

| Later move | Cost |
|---|---|
| add an import map | additive — change specifiers on import lines only; relative imports keep working alongside, so migrate file by file |
| custom elements for mounting | changes how an adapter *mounts*, never its vendor glue; per-adapter |
| add a bundler | the easiest — Vite and esbuild consume ESM natively; add a config, change the script tags, **the source does not change** |
| globals | mechanical but touches every file; no reason to |

**Format is cheap to change; architecture is not.** Modules-versus-globals is a find-and-replace. The client/adapter boundary (§7.4) is structural, and that is where the care belongs.

### 7.6 The client is a consolidation, not new code

Its pieces already exist, scattered across three places:

| Piece | Lives today in |
|---|---|
| `postJSON`, `postFormData` — the CSRF + JSON ceremony | `fetch-helpers.js` |
| `appendParams` — URL parameter building | `core.js` |
| `getCookie` — the CSRF token | `core.js` |
| `_destroyWidgets` — teardown before re-render | `core.js` |
| fetch, catch, loading, empty | duplicated in `table.js`, `kanban.js`, `gantt.js`, `pivot.js` |

`fetch-helpers.js` is the seed and its own comment records the instinct — it was extracted because the ceremony *"was duplicated across core.js, comments.js, attachments.js, checklist.js"*. It stopped at writes and never reached the four data widgets, which duplicated it again.

So the client is those rows gathered into one module: nine `fetch` calls become one, fourteen catch blocks become one error path.

### 7.7 `core.js` splits along the package layout

489 lines, twelve exports, five concerns — **from different layers**:

```js
export const plintaNotifications = {
    toggleDropdown: function() { fetch('/api/v1/notifications/dropdown/') ... }
```

That is `contrib.notifications` code inside core chrome — a contrib concern living in core, exactly the violation §4.10 tabulates on the Python side, somewhere the AST import test would never look. `setViewParam` writes `view_pb<id>` URL parameters, which belongs with `blocks` rather than in the chrome file.

| Exports | Goes to |
|---|---|
| `appendParams`, `getCookie`, `_destroyWidgets` | **the client** (§7.4), with `fetch-helpers.js` |
| `showToast`, `_getOrCreateModal` | core chrome — `ui/toast.js`, `ui/modal.js` |
| `openEditFromCell`, `openEditForm`, `openCreateForm`, `saveEditForm` | **`blocks`** — block write UI, not chrome |
| `navigateWithScroll` | core chrome — `nav.js` |
| `setViewParam` | **`blocks`** — it selects a saved view |
| `plintaNotifications` | **`contrib.notifications`** |

#### The rule

**The JS mirrors the package layout.** A component's adapter ships with its component; a contrib app's front-end code ships with that app; core carries the client and the chrome, and nothing else. Same layering as the Python, same one-way rule.

**And the import-boundary test covers JS too.** A regex over import paths is cruder than the Python AST walk, but it would have caught both violations above. Without it the front end drifts freely while the back end is policed — which is how these two got there.

### 7.8 The field-renderer extension point

Replaces four duck-typed model protocols (§21) with one registration.

Today a model may implement `serialize_for_table()`, `table_select_related()`, `expand_for_table()` or `expand_color()`, discovered by `hasattr`. §1 promises plinta requires nothing of a consumer's models; these are the same imposition under another name, and only `Label` implements any of them.

A field renderer is registered, declares how a value renders, and **declares what it needs joined** — which is what §6.5 depends on for prefetch derivation to see relations no column names.

```python
@register_field_renderer("label_chips", prefetch_related=["labels"])
def label_chips(value, *, obj, field, user) -> str: ...
```

**A column names one**, in `DataSourceField.renderer`, so binding is configuration like every other display option (§6.8) rather than a property of the consumer's model. Unset formats the value.

**The declared joins are the reason it is a registration** and not a duck-typed method. Derivation sees column paths; a renderer reaching `obj.labels` from a column called `title` is invisible to it. `joins_for(columns)` returns them, and they reach `get_queryset` as `extra_select` and `extra_prefetch`.

**Field renderers produce HTML.** A chip is markup and a spreadsheet cell is not, so other formats call `format_value` instead. Output is trusted: registering a renderer is the same trust as writing a template.

**A column naming an unregistered renderer is a boot error** (`plinta.renderers.E001`). It would otherwise raise one row into the page, having also silently lost the joins it declared. The check lives here because `datasources` cannot see the registry.

`expand_for_table` and `expand_color` are dropped with `expand_columns`.

### 7.9 Decisions

| Item | Decision |
|---|---|
| Renderer contract, registry, HTML in core | keep |
| Excel / PDF / email renderers | **→ `contrib.export`** |
| Shared format helpers, incl. `decimals` | core `renderers` |
| Component contract: config in, HTML out | keep, with the merge moved up |
| Per-component view CRUD and `_XViewSaveIn` parsers | **deleted** — a symptom of the misplaced layer, not duplication to factor |
| `AJAX` class constant | **→ mode: component default, block override** |
| `chart_plotly`, `kpi_plinta`, `gauge_plotly` mode | **inline** — changed |
| Inline data location | a defined JSON script tag beside the mount |
| The widget data endpoint | **private transport** — a Django view returning JSON, not ninja |
| Widget feed vs public API | **kept separate**; they share `datasources` underneath, not a URL |
| Block-shaped output for a caller | the **export path** with a registered `('table', 'json')` renderer |
| Applying a saved filter by id | **the caller expands it** — publish `FilterSet` with `show_in_api`; no registry |
| Write request bodies | **`application/json` only** — another content type is a 415 (§15.3); file upload is the one multipart endpoint |
| Per-widget fetch/error/loading code | **→ one shared client** |
| `serialize_for_table` / `table_select_related` | **→ registered field renderer** |
| `expand_for_table` / `expand_color` | **dropped** |
| Module format | **ES modules** — already the practice; import map when bare specifiers or hashed storage bite |
| The shared client | a **consolidation** of `fetch-helpers.js` + three `core.js` exports + four duplicated widget paths |
| `core.js` | **split along the package layout**; two contrib concerns move out |
| JS file placement | mirrors the package layout — adapters with components, contrib JS with its app |
| Import-boundary test | **extended to JS** |


## 8. Layer 7 — blocks



Build layer 7. A Block is a saved component configuration bound to a DataSource. Blocks also own **the write pipeline** — the single path by which plinta mutates a consumer's data.

**May import:** `utils`, `dates`, `events`, `permissions`, `datasources`, `renderers`, `components`.
**Must not know:** what a Page is, or that any contrib package exists.

### 8.1 The model

| Field | Decision | Note |
|---|---|---|
| `name` | keep | unique per owner — which is why grants are pk-keyed (§5.10) |
| `component_type` | keep | a registry key; an unregistered value renders an empty slot |
| `data_source` | keep | FK; a block cannot exist without the model it reads |
| `config` | keep | JSON, validated against the component's schema with `extra='forbid'` |
| `base_filter` | keep | locked filters, always applied; honours placeholders (§3.6) |
| `queryset_modifier` | keep + **fix help text** | see below |
| `description`, `icon` | keep | |
| `owner` | keep | `null` = public (§5.8) |
| `is_active` | keep | |
| `mode` | **add** | `inline` \| `fetch`, overriding the component default (§7.3) |

#### `SavedView` lives here

A saved view is a **delta over a Block**, so it belongs with blocks (§14.3a).

| Field | |
|---|---|
| `block` | **FK** — today a `block_name` `CharField` |
| `name`, `config` (the delta), `owner`, `is_default` | keep |
| `view_type` | **dropped** — derivable |

**`block_name` → `block` FK.** It is the last place the name-as-reference defect survives; §5.10 fixed it for permission codenames, §8.10 for URLs, §9.3 for page composition.

Three things it fixes:

- **Renaming a block silently orphans every saved view on it.** The string stops matching, so views disappear from the picker with no error and no way to notice. This is the strongest reason, and it is the same bug the instance-permission re-key already fixed for grants — that one was caught, this one was missed.
- **Ambiguity.** Two blocks named `instruments-table`, one private and one public: a saved view on that name matches both.
- **Orphans.** A deleted block leaves rows matching nothing. `on_delete=CASCADE` — a view of a deleted block is meaningless.

**`view_type` goes with it.** It is the component type of the view, which with a block FK is `block.component_type`; a chart view on a table block cannot legitimately exist, so the two can never differ. Today it is carried in the unique key, both composite indexes and the ordering — all of which shift to `block`.

`SavedView` becomes `(block, name, owner, config, is_default)`, with `unique_together = ('block', 'owner', 'name')`.

**The cost is signature churn**, not risk: `get_available_views(block_name, user)`, `_accessible_view_q`, `_view_queryset` and the seven endpoints `router_factory` generates per component type all take a name today — most of the 173 `block_name` references in the components package. Mechanical, and there is no existing data to migrate.

Saved views are shareable on the same rules as blocks, and gain share, copy and push (§5.10).

**This is the only name-as-reference left.** Swept: `DataSourceField.data_source` is already an FK; the four `field_name` fields correctly hold a Django field *path* (`company__code`), which is not a row in any table; `Page.template_name` is a template path; `ScheduledReport.report_code_name` is already dropped (§14.1).

**`queryset_modifier`'s help text is stale.** It reads *"Dotted path to a function that modifies the queryset"*, but modifiers are **registered by name** and an unregistered name hard-fails at save (§6.4). The field stores a key, not an import path. This is one of the four instances of documentation drift §21 records — fix the text with the field.

Blocks are shareable: `Owner | Public | InstancePerm` to view, `Owner | InstancePerm` to change.

### 8.2 Rendering

`render_block(block, user)`:

1. **Resolve the effective config** — the block's config merged with the viewer's `SavedView` delta. No hook and no optionality: this layer owns both models (§8.1).

   **Which delta, when the viewer chose none:** their own default, then a public default, then none — leaving the block's own config. Both steps are a mark someone made deliberately. Falling back further, to whichever view sorts first, would let adding a view silently change what everyone sees; the block config is the explicit base and is what an admin edits to change it.

   A **public default** is how someone holding `change_savedview` but not `change_block` curates a starting view. The chain runs through `allowed`, so it can never surface a view a policy hides.
2. **Look up the component.** Not registered → empty slot, not an exception.
3. **Fetch** rows and fields through `datasources`, passing the user.
4. **Call the component** with the resolved config (§7.2).

Step 1 is the layer boundary that keeps personalisation out of components. Step 3 is why a block cannot widen access: the narrowing already happened below it.

**A page of blocks costs a constant per block**, and the page's own reads — the permission cache, the filter controls, the placements — are paid once however many blocks it holds. That is inline's advantage over fetch and the reverse of the usual assumption: four fetched blocks are five requests, each rebuilding the viewer's permission cache, where four inline blocks are one request that builds it once.

Pinned by a test, because the failure mode is a query per placement that only appears on a real dashboard.

`mode` decides whether step 3 runs now or the client fetches later (§7.3) — the same `get_data()` either way.

### 8.3 The write pipeline

Every mutation goes through it. The current implementation is fifteen stages for edit and sixteen for create, composed by the API handlers.

**Ordering invariants that must survive the rebuild:**

- permission stages gate **before** any validation or mutation stage
- `full_clean_and_save` runs **before** M2M application — M2M needs a pk
- a workflow transition executes **last** among writes, so hook-stamped fields are not clobbered
- `create_defaults` overlays `base_filter`, so defaults win on conflict

**The v2 shape**, with the audit and notification stages replaced by events:

| Stage | |
|---|---|
| 1 | authorise — model permission, instance policy, then field permission per field written |
| 2 | coerce and validate — through the model layer, never around it |
| 3 | emit `object_writing` |
| 4 | save, then apply M2M |
| 5 | compute `changes` — `{field: (before, after)}`, including M2M |
| 6 | emit `object_written` |

Deletes follow the same authorise-then-emit shape. There is no restore signal — §8.10.

**A denied field is refused, not dropped.** Writing a field the user may not change raises, naming every field refused, rather than saving the rest — a partial write reported as a success is the worse answer.

**The diff's `before` is read from the database**, not from the instance, which already carries the new values by the time the write runs. A field whose value did not change is absent from `changes`; on create every written field appears with `None` before it.

**Three stages disappear into events.** `sync_labels`, `fire_notifications_stage` and `audit_changes` are stages 12–14 today — the three listeners in disguise (§4.10). They become subscribers, and the pipeline stops importing `labels`, `notifications` and `audit`.

**One stage stops being conditional.** `attach_recompute_siblings_row` is gated by a DSF flag with zero uses, and without the flag an inline edit returns no updated row at all. The **flag** goes, not the behaviour: the refetch becomes unconditional, so a write always returns the saved row (§21).

**Why core computes the diff** is recorded in §4.2: core performs the write and therefore already knows. That is what makes `audit` a listener rather than a stage.

### 8.4 `base_filter` and `queryset_modifier`

Two different narrowings, both on the Block:

- **`base_filter`** — locked filter *values*, always applied, invisible to the viewer. A filter-style dict, so placeholders resolve (§3.6).
- **`queryset_modifier`** — a registered named callable that transforms the queryset. May narrow, must not widen (§6.4).

Both are **configuration**, chosen by whoever builds the screen, not by the viewer. That is what distinguishes them from page filters, which the viewer drives.

**They reach a component as one opaque callable.** `blocks` composes them into a `narrow(queryset) -> queryset` and passes it to `get_data`, which applies it after `datasources` has filtered. So a component applies a block's narrowing without learning that blocks exist, and the ordering — policy first, then configuration — cannot be got wrong per component.

**An unresolved placeholder is left as written**, so a `base_filter` naming a token nothing registered matches nothing. Dropping the clause would widen the filter it was written to narrow.

**An unregistered modifier raises** rather than being skipped, for the same reason: a modifier exists to hide rows, and skipping a missing one shows every row it was meant to exclude.

**"May narrow, must not widen" stays a rule its author keeps.** The callable is opaque, so a modifier that starts from `Model.objects.all()` defeats the row policy — which is why `add-queryset-modifier` states the rule and gives the one-line subset test that catches it.

### 8.5 Capabilities

The registry lives here — `blocks/capabilities.py` — because a capability contributes to an **edit form**, which is a block concern.

**Two registrations exist today and only one is done right:**

| Kind | Registered by | Verdict |
|---|---|---|
| edit-form | the owning app — `attachments`, `audit`, `checklist`, `comments`, `labels` | ✅ correct |
| matrix | **core `pages`**, centrally | ❌ backwards |

`pages/capabilities.py` defines probes for **seven contrib apps** — actions, comments, attachments, checklist, labels, workflow, notifications — and registers their matrix rows itself. Six survive; the actions probe leaves with its app. That is core knowing contrib by name, and it is why that file imports `notifications.triggers._handlers` (§4.9).

`audit` registers **both** its own, so the correct pattern already exists in the codebase, applied once.

**Decision: each app registers its own capability, both aspects, as `audit` does.** Core `pages` then renders whatever is in the registry and knows none of them.

The two probe signatures stay different, and legitimately so — the edit-form probe answers *"does this apply to this object?"*, the matrix probe answers *"does this model support this at all?"*. Different granularity, different question. What is removed is registering the same capability from two places, one of which is the wrong layer.

The matrix's precomputed `state` argument — which exists so each probe stays O(1) rather than issuing a query per model — survives as an optional `prepare()` on the capability.

### 8.6 Checks this layer registers

**Unresolved placeholder tokens** in `Block.base_filter` and in `create_defaults`
(§3.6). `utils.unresolved(values)` names the tokens nothing has registered; this
layer walks the Blocks, because `utils` cannot read one.

A token with no provider is left in the filter verbatim rather than blanked — so
without this it fails silently, matching nothing rather than widening. That
choice is what makes the check necessary.

A `django.core.checks` function, like the other four (§20.3). Reading rows is no
obstacle: a check that queries returns nothing on a `DatabaseError`, since
failing there would block the migration that fixes it.

### 8.7 What this layer owns

The block CRUD and inspector API, the write endpoints, the data endpoint that serves `fetch`-mode components (§7.3), the capability registry, and block sharing.

It does **not** own: the export endpoint (`contrib.export`, §14) or anything a page does with a block.

### 8.8 Decisions

| Item | Decision |
|---|---|
| `base_filter`, `queryset_modifier` | keep — configuration-level narrowing |
| `queryset_modifier` help text | **fix** — it stores a registered key, not a dotted path |
| Union validation errors | **collapse here** — pydantic reports one error per union branch, so a bad `base_filter` value yields five messages under one field. `loc[1]` names the branch; collapse to one message stating the rule, which only this layer can word |
| `mode` on the block | **add** — overrides the component default |
| Capability probes | **both registered together**, by the owning app; `prepare` runs once per capability, not once per model |
| `sync_labels`, `fire_notifications`, `audit_changes` stages | **deleted** — become event subscribers |
| `recompute_siblings` flag | **dropped**; the refetch becomes unconditional — the capability stays |
| Capability registry location | stays in `blocks` |
| Matrix capabilities registered by `pages` | **moved to the owning apps** |
| Blocks resolving components by registry key | keep; unregistered → empty slot |
| Delete | **hard** — plinta calls `obj.delete()`; soft delete is the model's own override |
| `object_restored` | **dropped** — a restore is an update; five signals, not six |
| `duplicate(user)` model hook | **keep** — opt-in, natural, `shallow_copy` default |
| `copy_to` vs `duplicate` | **separate verbs** — copy a shareable, duplicate a row |
| `duplicate_page` | **deleted** — `copy_to` walks declared children |
| Bulk write endpoints | **not in core** — a contrib importer loops the pipeline inside `events.batch()` |
| Block addressing | **by id**; the by-name endpoints and their resolution order are removed |
| `/export/`, `/pivot/export/` | **move to contrib** |
| `/actions-inline/` | **deleted** with `actions` (ADR 0008 (§24)) |

### 8.9 The inspector, and the form engine inside it

**The inspector stays in `blocks`.** It edits a core model and its endpoints are block endpoints. But a third of it does not belong to blocks at all.

`components/block_settings/api.py` is 667 lines and already **derives its form from the pydantic config schema** rather than hand-writing one per component type — `_walk_schema` iterates `schema_cls.model_fields`, `_widget_for_annotation` picks a widget from the type annotation, `_coerce_value` and `_parse_form_to_config` parse the POST back.

| Lines | What | Generic |
|---|---|---|
| ~205 | schema → form → parse back | **yes** |
| ~90 | block context, sharing card, per-field permission, template overrides | no |
| ~340 | the five endpoints — save, create, delete | no |

**Decision: extract the form engine.** It knows pydantic and HTML and nothing about plinta's domain, so it passes §3.1's admission test for the bottom of the stack — a `forms` package alongside `utils`. The block inspector, page settings, `FilterSet` editing and any contrib app editing a schema-backed config then render from a declaration instead of hand-building a form.

**Rejected: a generic authoring CRUD registry.** The endpoints genuinely differ — share, set-default and duplicate apply to some editable types and not others — and `saved_views/router_factory.py` already generates that family. Per §20 a new registry must be worth its weight, and the repetition here is in the **form**, not the endpoints.

**To verify when §14 reaches personalisation:** saved views and filter sets are not schema forms today — a saved view's editor is column-visibility UI. They benefit from the engine only where they edit a schema-backed config, which is `values` for `FilterSet` and the delta for `SavedView`. Check rather than assume.

### 8.10 Delete, duplicate, bulk, and block identity

#### Delete is hard, and `delete()` is the model's business

Plinta calls `obj.delete()`. What that means belongs to the model.

Core does **not** implement soft delete. Doing so would force every queryset in `datasources` to filter a deleted flag, and would impose a column on a consumer's models — which §1 says plinta never does.

A consumer wanting soft delete overrides `delete()` on their own model, which is ordinary Django. Plinta neither knows nor cares, and `object_deleted` fires either way.

**Consequence, stated because it surprises people:** with a hard delete the audit row is the only remaining trace that a record existed. That is why §4.2's create rows carry their initial values in `metadata` — without it, a created-then-deleted record leaves a log that cannot reconstruct what it was.

#### `object_restored` is dropped — five signals, not six

Nothing in plinta restores anything, and `audit.services.record_restore` is called by nobody; its own docstring describes it as *"the symmetric companion to `record_delete` for consuming projects"*.

A consumer with soft delete flips a flag, which is an **update**: `object_written` with `changes={'is_deleted': (True, False)}`. That is strictly more informative than a bare "restored" row, because it names the field and both values.

So the signal is removed and `record_restore` with it. §4.1's vocabulary is five signals.

#### Copying a shareable is not duplicating a row

Two different things share the word "duplicate" today, and they should not.

| | **Copy** a shareable | **Duplicate** a row |
|---|---|---|
| Copies | plinta configuration — a Block, a Page | the consumer's data — an Instrument |
| Owner | reassigned to the copier | unchanged |
| Children | its owned config children | M2M only |
| Lives in | the sharing spine (§5.10) | the block write path |

**Copy is already generic.** `permissions/sharing.py` has `copy_to(obj, owner, name=None)`, `can_copy`, and a content-type-keyed endpoint — working for Block, SavedView and FilterSet.

**The gap is children.** `pages/services.py::duplicate_page` is a parallel implementation, existing only because copying a Page must copy its `PageBlock` and `PageFilter` rows and generic `copy_to` copies one row. So: **a model declares its owned children and `copy_to` walks them**, the same shape as `register_share_lifecycle`. `duplicate_page` then deletes itself and `Page` declares its children instead.

**Naming: `copy` for shareables, `duplicate` for rows.** They are unrelated operations and the shared verb is what invites someone to unify them.

#### Duplication: a documented model hook, kept

`POST /blocks/{id}/duplicate/` copies a row. Core's default is `shallow_copy` — every concrete non-auto field, no pk — and a model may override by defining `duplicate(user)`.

**This one stays**, unlike the table protocols removed in §7.8. The difference is that `duplicate()` is a natural method on your own model, opt-in, with a working default if absent — where `expand_for_table()` required knowing plinta's rendering internals and did nothing useful alone.

M2M is copied; reverse relations are not. A model needing deep copy implements `duplicate()`.

#### Bulk writes are not core

There is no bulk edit or delete endpoint today, and core does not gain one. **The write pipeline is single-row by design** — it authorises, validates and emits per row, and those guarantees are what make it the only mutation path.

Bulk arrives as a **contrib importer**, which loops the pipeline inside `events.batch()` (§4.6) so listeners coalesce. That keeps per-row authorisation and per-row audit while making 5,000 rows cost one notification digest and one bulk audit insert.

A bulk path that bypassed the pipeline for speed would bypass permissions with it. It is not offered.

#### Blocks are addressed by id, not name

**Endpoints take the block's primary key.** `/blocks/{id}/data/` — not `/blocks/{name}/data/`.

`Block.name` is unique *per owner*, so a name does not identify a block: a user's private "instruments-table" and a public one collide. Today `get_block(name, user)` resolves that with an ordering — own, then public, then shared — which is a rule nobody can infer from a URL, and it means the same URL returns different rows for different people.

Both forms exist today (`/{name}/data/` and `/by-id/{id}/data/`). The by-id pair is kept and the by-name pair removed, which deletes the resolution rule rather than documenting it. Names remain for display and for authoring UIs, where the owner is known.

This is the same reasoning as §5.10's pk-keyed instance permissions and §9's blocks-resolved-by-FK: an identifier that is unique only per owner cannot address a shared resource.

#### What leaves this layer

Three endpoints in `blocks/api.py` belong elsewhere and move with their apps:

| Endpoint | Goes to |
|---|---|
| `/{name}/export/` | `contrib.export` |
| `/by-id/{id}/pivot/export/` | `contrib.export` |
| `/actions-inline/{ct}/{obj}/` | **deleted** — its model leaves plinta (ADR 0008 (§24)) |

Core's block API is then: list, search, data, edit-form, write, delete, duplicate, and the inspector.


---

## 9. Layer 8 — pages

Build layer 8. A Page composes blocks into a screen, gives them a shared filter bar, and places that screen in the menu.

**May import:** every core layer below it.
**Must not know:** that any contrib package exists.

### 9.0 Addressing: id-authoritative, slug decorative

`/pages/<id>-<slug>/`. The **id** resolves the page; the slug is ignored on lookup and exists to make the URL readable.

`Page.slug` is unique *per owner* today, which has the same defect §8.10 found in `Block.name`: a per-owner identifier cannot address a shared resource, so `/pages/catalog/` resolves to a different page depending on who asks.

**Global slug uniqueness was considered and rejected.** In an organisation of 500 people it would require them to negotiate over `my-dashboard` — the identifier's scarcity would become a user-facing problem, which is never an acceptable trade for a naming convenience.

Id-authoritative addressing gives all three properties: everyone may name a page `my-dashboard`, a shared link always resolves to the page that was shared, and a rename does not break existing links. Slug uniqueness stays per-owner, so a person's own pages remain distinguishable in their menu.

This is §8.10's rule with a nicer surface: address by id, let names be for humans.

### 9.1 Models

| Model | Is |
|---|---|
| `Page` | a composition of blocks, with a filter bar and a menu placement |
| `PageBlock` | a block placed on a page at a grid position |
| `PageFilter` | one control on the page's filter bar |
| `MenuSection`, `MenuGroup` | navigation placement |

`FilterSet` and `PageFilterPreference` live here too — saved filter values and remembered filter state are per-user deltas over a page, and a page is what they are deltas over.

#### `Page` fields

Usage across a live install of 36 pages:

| Field | Used | Decision |
|---|---|---|
| `name`, `slug`, `description` | — | keep; slug is decorative (§9.0) |
| `page_type` | 36 | keep — dashboard 27, custom-template 7, detail 2 |
| `owner` | — | keep — `null` = public |
| `show_in_menu`, `menu_order`, `menu_icon`, `menu_group` | 33 | keep |
| `template_name` | 7 | keep — how `custom-template` resolves |
| `context_param` | 2 | keep — the URL parameter a detail page binds |
| `primary_data_source` | — | keep — the model a detail page shows |
| `tabs` | 1 | keep — see below |
| `config` | 0 | keep — the contrib extension slot |
| `is_active` | — | keep |
| `is_system` | **0** | **drop** |
| `external_url` | **0** | **drop** |

**`is_system` — drop.** It exists to stop someone deleting a page plinta needs, and implements that by branching `PagePolicy` on `is_system=False` for change and delete. That is a flag acting as a permission, which §5.8 removes everywhere else. The replacement is the permission itself: do not grant `delete_page` to people who should not have it. And §16's `loadconfig` restores deleted configuration, so the failure it guards against is recoverable.

**`external_url` — drop.** A Page whose only job is to link elsewhere is a menu item, not a page: it has no blocks, no filters and no grid. `get_absolute_url` currently checks it first and short-circuits slug routing, so it is a second routing mode hiding inside the model. A menu link to an external URL belongs on the menu.

**`tabs` — keep, with a note.** A page may render nav tabs above its blocks, and the active tab flows to blocks as a request parameter. Its one consumer, plinta's own actions page, leaves with `actions` (ADR 0008 (§24)), so it ships with zero users. It survives because tabbed pages are conventional, the alternative is a page per tab, and the filtering it drives is an ordinary `queryset_modifier` — the mechanism costs a request parameter and a template block.

**`config` — keep as the extension slot.** Zero rows set it, but `get_applicable_reports` reads `config['reports']`. With reports becoming contrib, a contrib package needs somewhere to put page-level settings, and this is it. Contrib writes namespaced keys; core never inspects them.

### 9.2 Page types

| Type | Renders |
|---|---|
| `dashboard` | blocks on a 12-column grid |
| `detail` | blocks scoped to one record of `primary_data_source`, plus whatever each installed app contributes |
| `custom-template` | a named template — used for account settings, the permission console, the capability matrix |

`custom-template` is the escape hatch, and it is where plinta's own non-composed screens live. It is not a general-purpose CMS: the template is a path plinta or a consumer ships, not authored content.

#### How a detail page reaches its record

**In the path** — `/pages/<id>-<slug>/<record>/` — so the URL is the thing somebody sends a colleague. `context_param` names a query parameter that may carry it instead, for a page reached from another system as `?book=7`.

**The record reaches a block through `__RECORD__`**, a placeholder resolving to its primary key. A placement writes `context_filter={"pk": "__RECORD__"}` or `{"book_id": "__RECORD__"}`, and one placement then serves every record the page shows.

That is the whole mechanism: no second filtering path, no context object threaded through components, and `utils` still knows nothing about pages — `Context` carries a value, and `pages` registers the token that reads it.

**A record the viewer may not see is a 404**, like the page itself. Saying a record exists but is not theirs is a disclosure.

**Capability sections are drawn here and only here.** A detail page asks the registry what applies to this row and includes each template; a dashboard has no row, so it draws none. Core names no capability — an installation with no contrib app draws nothing, and that is the same code path.

### 9.3 Composition

`PageBlock` places a block at a grid position and carries its own title, visibility and context filter. It travels with its page, is never independently shareable, and the same block may appear on several pages at different sizes.

**Both coordinates are stored**, in grid cells: `column`, `row`, `width`, `height`. The layout has no gravity — a block stays exactly where it was dropped, rather than floating up to close a gap — so a row cannot be derived from the order. `order` survives as a tie-breaker and as the sequence on a page with no grid.

The position is written by drag and resize in the browser and read straight into CSS grid; nothing recomputes it server-side.

**Blocks resolve by foreign key**, never by name — §8.10's reasoning, applied here: a name is unique only per owner and cannot address a shared resource.

**Three degradations. Two are normal states; the third is a failure that is contained rather than propagated:**

| Cause | Slot shows |
|---|---|
| the viewer may not see the placed block | empty slot |
| the component type is not installed | empty slot |
| the block **raised** while drawing | a message in that slot |

Making a placed block private, or uninstalling a component, must never break the page that holds it — and neither must a misconfigured block. A dashboard of eight going dark because one names a config key its component dropped is the failure this prevents.

**Contained, not hidden.** The original exception is logged with its traceback and re-raised as a `BlockRenderError` naming the block, so the page can put a message in one slot and draw the rest. **In `DEBUG` it is not caught at all**: a developer wants the traceback, not a tidy card.

### 9.4 The filter bar

`PageFilter` declares which fields a page exposes as controls, with a widget and a lookup. It is **page furniture**: always visible, no permissions of its own, and driven by the viewer rather than by configuration — which is what distinguishes it from `base_filter` and `queryset_modifier` (§8.4), both chosen by whoever built the screen.

Filter *values* are personalisation and live here as `FilterSet` and `PageFilterPreference` — the same delta-over-a-base shape `SavedView` has over a Block.

Filter values honour placeholders (§3.6), so `__CURRENT_QUARTER__` resolves at query time — and is **stored as written**, so a remembered filter keeps meaning the current quarter rather than freezing to the one it was saved in.

**Which values apply when the viewer sent none:** their remembered state, then their own default `FilterSet`, then a public one, then each control's own `default_value`. The same chain shape as a block's saved view (§8.2), and for the same reason: every step is a mark someone made.

**A value for a field the page does not declare is ignored.** The bar is what the page exposes; a query string is not, and honouring an undeclared key would let a URL filter on a column the page never offered.

**`PageFilterMapping` — keep, deferred.** It lets one filter drive blocks over *different* DataSources, mapping to a different field path on each — so a single "sector" control filters an instruments table on `sector`, a prices chart on `instrument__sector`, and a fundamentals block on `instrument__sector__code`.

Zero rows, but it is `pages/0003` — the most recent pages migration — so it is **new, not dead**. §21's rule applies: zero uses is evidence, not proof.

The mechanism is not built in layer 8. A page whose blocks share a DataSource needs nothing, and a mixed page can declare a filter per source in the meantime. It returns when a dashboard actually needs one control across several models, which is the case it was written for.

### 9.5 The menu

`MenuSection` contains `MenuGroup` contains pages.

The menu is assembled from **pages the viewer may see**, so it is permission-filtered by construction rather than by a second configuration. A page the viewer cannot open never appears.

`admin_only` on a section or group is the same defect as `is_system`: a flag acting as a permission. It goes; visibility follows from the pages inside it, which are already permission-filtered.

### 9.6 Checks this layer registers

**Unresolved placeholder tokens** in `PageFilter` values, `FilterSet.values` and
`PageFilterPreference` (§3.6) — the same shape as §8.6, over the dicts this
layer stores.

### 9.7 What leaves this layer

**The capability matrix registrations.** `pages/capabilities.py` defines probes for seven contrib apps and registers their matrix rows centrally, which is why it imports `notifications.triggers._handlers`. Six of the seven survive — the actions probe leaves with its app — and each registers its own (§8.5); pages renders a registry it knows nothing about.

**The account-settings organisation cards.** `_get_account_settings_context` reads `usercompanyaccess_set` — org concepts in a core view. They move to `contrib.organization`, which contributes them to the page.

**`duplicate_page`.** Replaced by `copy_to` walking declared children (§8.10).

### 9.8 Decisions

| Item | Decision |
|---|---|
| Addressing | `/pages/<id>-<slug>/`, id authoritative (§9.0) |
| `is_system` | **drop** — a flag acting as a permission |
| `external_url` | **drop** — that is a menu item, not a page |
| `admin_only` on menu section/group | **drop** — visibility follows the pages inside |
| `PageFilterMapping` | **deferred** — new, not dead; one control across several models |
| `FilterSet`, `PageFilterPreference` | **stay in `pages`** — deltas over a page |
| `tabs`, `config`, `template_name`, `context_param` | keep |
| Blocks resolved by FK | keep |
| Unviewable block / uninstalled component | empty slot, not an error |
| Matrix capability registrations | **→ the owning apps** |
| Account-settings org cards | **→ `contrib.organization`** |


---

## 10. Layer 9 — the shell

Build layer 9. The chrome every screen renders inside, and the only layer a browser touches before a page.

**May import:** every core layer below it.
**Must not know:** that any contrib package exists.

### 10.1 The base template

One base template, not two. Today `plinta/templates/plinta/base.html` and `plinta/templates/shell/base.html` both exist and `seed_platform_pages`' docstring names the second while the pages render through the first. **v2 ships one**, under `shell/`.

It provides: the document head and asset loading, the topbar, the sidebar, the theme toggle, and the blocks `body` / `extra_css` / `extra_js` a page fills.

**Not the notification bell.** A bell is `contrib.notifications`', and a base template that drew one would be core naming a package that may not be installed — the line §10 draws in its own `Must not know`. The shell offers a **topbar registry** instead and renders whatever is in it, exactly as it does for the sidebar's fixed links (§10.2).

```python
register_topbar_item(
    "notifications",
    template="plinta/notifications/bell.html",
    permission="plinta_notifications.view_notification",
)
```

An item naming a permission is drawn only for a holder, so an app's chrome disappears with its access rather than showing a control that refuses.

**One base, and its regions in separate files**, because a template is the unit someone overrides (§10.9). v1's single file meant changing the sidebar required forking the document head with it.

Shipped by the `shell` app — it is what renders them — and namespaced under `plinta/`, so the path a consumer shadows is unambiguous:

| Template | Is | Blocks it carries |
|---|---|---|
| `plinta/shell/base.html` | the document, the head, the three regions | `plinta_css`, `extra_css`, `topbar`, `sidebar`, `body`, `extra_js` |
| `plinta/shell/topbar.html` | brand, theme toggle, user menu | `topbar_brand`, `topbar_actions` |
| `plinta/shell/sidebar.html` | the menu tree and the fixed links (§10.2) | `sidebar_header`, `sidebar_menu`, `sidebar_footer` |
| `plinta/shell/messages.html` | toasts | — |
| `plinta/pages/page.html` | the grid wrapper and the filter-bar slot | `page_header`, `page_filters`, `page_body` |
| `plinta/pages/block.html` | the card around one widget | `block_header`, `block_body` |
| `plinta/pages/filter_bar.html` | the controls, chips and saved-set picker | `filter_controls` |
| `plinta/shell/auth_base.html` | the document for a viewer who has not signed in | `auth_title`, `auth_header`, `auth_body` |
| `plinta/auth/login.html` and four password-reset templates | Django's auth views with plinta chrome | `auth_body` |

Ten files, so `base.html` is about thirty lines of document and three includes rather than a monolith. The auth screens render **outside** the shell: there is no menu to draw for someone who has not signed in, so they extend their own document rather than blanking three regions of `base.html`.

**Dropping a region is a block, not a fork.** `{% block sidebar %}{% endblock %}` removes the sidebar without touching anything else; shadowing `plinta/shell/sidebar.html` replaces its markup; extending it and overriding `sidebar_footer` adds a link while the rest keeps updating.

**This table is the contract.** The block names above and the context each template receives are public API (§18.16), and are the reason the file split is fixed here rather than left to taste.

### 10.2 The sidebar

Two sources, and both belong here:

| Source | Contents |
|---|---|
| `Page` records | menu sections and groups, permission-filtered per viewer (§9.5) |
| Fixed links | the authoring screens — Blocks, Data Sources — which are not pages |

Fixed links are rendered by the shell, so they are permission-gated by the shell rather than by a `Page` row. A viewer without `view_block` does not see the Blocks link.

**Registered, not listed in the template.** A screen declares its own link — label, URL name, the permission it needs — so the shell does not name packages it does not own, and a link cannot outlive the app behind it. The gate is a plain `has_perm`: these screens are views rather than rows, so there is nothing for a policy to narrow.

#### The sidebar takes links; the topbar takes templates

Two registries, deliberately different shapes.

| | shape | an app supplies |
|---|---|---|
| sidebar (§10.2) | **a link** | label, URL name, permission, icon, an optional count |
| topbar (§10.1) | **a template** | a path core includes |

**A nav where every entry looks the same is a feature.** Core owns the active state, the icon slot and the spacing, so one app cannot make the menu look broken. Arbitrary markup in the sidebar would give that away for a want nobody has.

**A topbar item is a different widget each time** — a bell with a count, a search box, an environment badge — so constraining it to a link would make a bell impossible.

**The one thing a link cannot say on its own is a number**, and "Reports 3" is the realistic want. A link may declare a `badge` callable, resolved per viewer before the template sees it, because a Django template cannot call a method with an argument. A count of zero draws nothing — a badge saying "0" is worse than no badge — and one that raises is logged and dropped, since a broken count must not take down the menu.

**Icons are a class name, not an icon.** Core draws whatever the installation's set uses and names none of its own, so a consumer's own icons work unchanged.

### 10.3 Authentication

The shell owns login, logout and the four password-reset views, mounted under its own namespace. They are Django's built-in auth views with plinta templates; plinta adds no authentication logic of its own and no user model (ADR 0002).

### 10.4 `LoginRequiredMiddleware`

Every request requires an authenticated user unless its path matches `PLINTA_LOGIN_EXEMPT_PREFIXES`.

This is plinta's own middleware and it is **required**, not optional: it is the outermost gate, and the layers below assume a request has reached them with a real user. The exempt list covers the login and password-reset paths and nothing else by default.

A consuming project adds it to `MIDDLEWARE`. **The shell registers its own system check** and errors if it is absent, because every permission decision below assumes it ran.

**And if it is installed too early.** Before `AuthenticationMiddleware` there is no `request.user` to inspect, so the gate lets every request through while appearing to be configured — the worse of the two failures, and the reason this is checked rather than documented. It is the shell's check rather than one of §5.13's, which are all about policy and codename registration — `permissions` does not know a middleware exists.

### 10.5 Context processors

Three today; two after the move below. They are the shell's data:

| Processor | Provides |
|---|---|
| `menu_pages` | the sidebar tree, permission-filtered |
| `branding` | `site_name` and `topbar_color` |
| `pivot_provider_settings` | which pivot vendor is active |

`pivot_provider_settings` is a contrib concern in a core processor. It moves: a pivot package contributes its own template context rather than the shell knowing a vendor exists — and with a package per vendor (§11) there is no provider left to settle.

`deployment_env` is renamed **`branding`**. Once the environment badge is deleted (§19.4) it returns a site name and a topbar colour, and a processor whose name no longer describes what it returns is the drift this document exists to stop.

### 10.6 Loading, empty and error

Three states, and v2 splits them by mode (§7.3) rather than giving every block all three.

| State | server-rendered inline | data-embedded inline | fetch |
|---|---|---|---|
| **loading** | none — the HTML arrives finished | none | the client's spinner |
| **empty** | the renderer draws it | the adapter | the adapter |
| **error** | the block card | the adapter | the client's alert |

**Loading is a `fetch` concern only.** An inline block has nothing to wait for, so a spinner over one is an animation for a state that never exists. The client owns the indicator, once, for the components that fetch (§7.4).

**Empty belongs to whoever draws.** For a server-rendered table that is the renderer, which is the only thing that knows the body came out empty. A table with an empty body reads as broken; one that says "No records" reads as a filter that matched nothing, which is what it usually is. A block may word it itself with `empty_text`.

**Error appears in the block's own slot** (§9.3), so a broken block is visible and localised rather than either silent or fatal. Over the wire it is the client's one error path; on the server it is the card.

### 10.7 Template tags

`plinta_tags` provides `site_name`, `get_item`, `classify_value`, `isodate` and `to_json`. All generic; all stay.

`comments_tags` ships with `contrib.comments`.

### 10.8 Theming

The shell owns the theme, and the theme is generated rather than written.

#### No CSS framework. Plinta styles its own screens.

**Decided.** Core emits its own class names — `pl-sidebar__link`, `pl-card`, `pl-table` — and ships one stylesheet built against the tokens. Bootstrap is not a dependency of core, of contrib, or of a consumer.

**Shipping Bootstrap as optional was considered and rejected.** Templates carrying `nav-link` and `btn` with Bootstrap absent are not degraded, they are unstyled, and §2.5 requires an `enhances` to name a substitute. "The page looks broken" is not one. Optional-but-assumed is worse than required.

**Once the class names are ours, a framework earns nothing.** Core's markup would never say `card` or `btn`, so Bootstrap would contribute a reset and a variable scale that `tokens.json` already holds.

**And a framework in core would break the cheapest override.** Retinting means redefining custom properties; with Bootstrap it means fighting its cascade or recompiling its Sass, which needs the build step §7.5 does not have. So a framework pushes consumers up the ladder (§10.9) to forking templates, where they stop receiving updates. Owning the CSS keeps most of them on the rung where they fork nothing.

**What it covers is bounded**, because it styles what plinta renders and nothing else — no utility classes, no layout system for arbitrary markup: shell chrome, the grid, the block card, table, form controls, buttons, modal, toast, filter bar, and the auth screens. Around ten components.

**`design/tokens.json` is the single source of truth.** `build_tokens` resolves its aliases, computes the `-rgb` companions a translucent surface needs, and emits:

- `static/plinta/css/tokens.css` — three blocks in order: `:root` for light, a `prefers-color-scheme` query guarded by `:not([data-theme="light"])`, then `[data-theme="dark"]`
- `static/plinta/js/tokens.js` — the chart palette and a `read()` helper

**The operating system decides until the viewer does.** The middle block follows the machine's setting; the guard means a viewer who explicitly chose light keeps light on a dark-mode machine, and the attribute block last means an explicit choice wins over both.

**A primitive is emitted as its own variable**, not inlined into the semantic that references it, so a browser's dev tools show which one a colour came from.

**A token asking for an `rgb` companion must be a primitive alias.** A computed value — `color-mix`, say — resolves in the browser, so its channels are unknowable at build time; asking is refused rather than answered wrongly.

`theme-toggle.js` switches `data-theme` and remembers the choice. It and `tokens.js` are the shell's only JS. The attribute is `data-theme`, not `data-bs-theme`: nothing about it belongs to a vendor.

**The shell ships no vendor theming.** `plotly-theme.js` maps tokens onto Plotly's layout, so it travels with the Plotly components (§7.4) and reads `tokens.read()` like any other consumer. The shell must not know Plotly exists, which is its `Must not know` line taken literally.

**`lint_hex_colors` enforces the rule**: no raw hex outside `tokens.json`. It runs in CI, because a single hardcoded colour breaks dark mode in a way nobody notices until someone switches.

**Contrib components read tokens, never colours.** A component wanting a series palette calls `tokens.read()`; it never ships a hex value.

### 10.9 Overriding, and what that costs

Four rungs, and the ladder only has its cheap ones because core owns its class names.

| Lever | Forks | Keeps receiving updates |
|---|---|---|
| redefine CSS custom properties | nothing | yes |
| replace the stylesheet, keep the markup | nothing | yes |
| extend a template, override one block | that block | yes, for the rest of the file |
| replace a template | that file | **no** |

**Replacing the stylesheet must not require forking `base.html`**, so core's own `<link>` sits in its own block:

```html
{% block plinta_css %}<link rel="stylesheet" href="{% static 'plinta/css/plinta.css' %}">{% endblock %}
```

A consumer wanting Bootstrap specifically loads it there and writes a bridge stylesheet, or overrides the templates they care about. Both roads stay open; neither is core's concern.

**Templates are split by override boundary**, not by taste: a separate file when someone would replace the whole thing, a block when they would change part of it. A forty-line `sidebar.html` is a cheap fork; a four-hundred-line `base.html` is not. `block.html` — the card around every widget — is the one most likely to be replaced, so it stays deliberately thin.

**Three things become public API**, with the same stability obligation as the Python (§18.16): the **class names**, the **context** each template receives, and the **block names**. Without that, "override the template" is a promise broken every release.

### 10.10 Decisions

| Item | Decision |
|---|---|
| Two base templates | **one**, under `shell/`, with its regions in separate files |
| CSS framework | **none** — core styles its own screens against the tokens |
| Bootstrap | **not a dependency**, not even an optional one (§10.8) |
| Theme attribute | `data-theme`, not `data-bs-theme` |
| Template granularity | split by override boundary; blocks for partial changes |
| Class names, template context, block names | **public API** (§18.16) |
| The notification bell | **contributed, not built in** — a topbar registry (§10.1) |
| `LoginRequiredMiddleware` | **required**, with a system check |
| Fixed sidebar links | shell-rendered, shell-gated |
| `pivot_provider_settings` context processor | **→ the pivot package that needs it** |
| `plinta_tags` | keep — all five are generic |
| Design tokens | keep — generated from `tokens.json`, enforced by `lint_hex_colors` |
| Dark mode | keep — `data-theme`, token-driven |
| Layout in view mode | **CSS grid from the stored position** — no JavaScript |
| GridStack | **edit mode only**, loaded on demand |

---

# Part III — What ships

## 11. The component catalogue



Thirteen components ship. **Core ships `table_plinta`; every other one is a contrib package** (ADR 0005), each carrying its own config schema, template, adapter and vendor.

| Component | Lives | Vendor | Mode | LOC |
|---|---|---|---|---|
| `table_plinta` | **core** | **none** | **inline** | 976 |
| `table_tabulator` | contrib | Tabulator | fetch | — |
| `kanban_plinta` | contrib | — | fetch | 1,106 |
| `pivot_webdatarocks` | contrib | WebDataRocks | fetch | 799 |
| `pivot_flexmonster` | contrib | Flexmonster | fetch | — |
| `gantt_jsgantt` | contrib | jsGantt | fetch | 735 |
| `chart_plotly` | contrib | Plotly | **inline** | 694 |
| `gauge_plotly` | contrib | Plotly | **inline** | 403 |
| `kpi_plinta` | contrib | — | **inline** | 365 |
| `details_card_plinta` | contrib | — | inline | 278 |
| `repeater_plinta` | contrib | — | inline | 269 |
| `text_plinta` | contrib | — | inline | 115 |
| `alert_plinta` | contrib | — | inline | 114 |

#### A component is named `capability_implementation`

**Decided.** `chart_plotly`, not `chart`. The capability says what it draws; the
implementation says what draws it.

**So two vendors are two packages, not one package with a setting.** v1 has a
`pivot` component holding both WebDataRocks and Flexmonster behind a
`providers.py` abstraction and a `PLINTA_PIVOT_PROVIDER` setting — an
indirection that exists only because one package was trying to be two things.
Splitting the name splits the package, and the abstraction, the setting and its
licence-key branch all go with it (§19.2).

**Each registers its own key**, so both may be installed while an installation
migrates from one to the other, and the registry's refusal of a duplicate
(§7.2) needs no exception. A block records which one draws it: reading
`component_type` tells you, where `chart` would not.

**`plinta` is the implementation name when we are the vendor** — `kpi_plinta`,
`alert_plinta`. Not decoration: it leaves the obvious name free for whoever
ships `kpi_acme`, and means a reader never has to know which components happen
to have an alternative today.

**Core's own follows the rule.** `table_plinta` sits beside `table_tabulator`
with no privilege in the registry, which is ADR 0005 (§24) made visible in the
name rather than only asserted in prose.

**The label is where the friendliness lives**: `register_component(
"chart_plotly", label="Chart (Plotly)")`, so a picker reads well while the
stored key stays exact.

Three modes change from today's `AJAX = True` — see §7.3.

### 11.1 Four cross-cutting simplifications

**One config schema per component.** Five of the seven `view_config.py` files are pure aliases — `from X.config import XBlockConfig as XViewConfig` — with only `table` and `pivot` genuinely differing. A component declares **one** schema, and a view uses it unless the component says otherwise. Deletes five files and the dispatch that imports them.

**No save-payload parser at all.** `chart`, `gauge`, `kpi`, `kanban` and `gantt` each define a near-identical `_XViewSaveIn` model *and* a `_parse_save_payload` that branches on `request.content_type`. With writes accepting JSON only (§15.3) the branch has nothing to select between, so what remains is one pydantic schema per component — which the component already declares (§11.1's first point). `ViewRouterSpec` gains `config_key` and needs no parser hook.

**Vendor config is namespaced, not flat.** `chart` carries eight Plotly layout keys — `margin_top`, `margin_bottom`, `margin_left`, `margin_right`, `x_tickangle`, `bar_gap`, `pie_textinfo`, `pie_textposition` — and `pivot` carries `formats` and `options`, which are Flexmonster's own structures typed as `dict[str, Any]`.

These are passthrough, not plinta's contract, and flattening them into `Block.config` makes the two indistinguishable. They move under a single `vendor` key: what plinta validates stays strict, what the vendor consumes stays opaque, and swapping a vendor touches one key rather than eight.

**Field-level formatting wins.** `kpi.decimal_places` duplicates `decimals` on `DataSourceField` (§6.8). The field-level declaration is honoured by every renderer; a per-component copy can only disagree with it. Dropped.

### 11.2 Per-component decisions

**`table_plinta`** — core, the reference implementation, and **server-rendered with no vendor at all**. `inline` mode: the rows are in the HTML.

Sorting, paging and filtering happen on the server, reached by ordinary links and the page's filter bar — `?sort=title&page=2`, the shape Django's own admin has always had. It works with JavaScript disabled and needs no client at all.

**A heading is a link and so is the pager**, built from the current query string rather than from nothing — so sorting keeps the filters, paging keeps the sort, and sorting returns to page one, because page four of a different order is a different four rows. Each placement's parameters are prefixed with its id, so two tables on one page sort independently.

**A column the viewer may not see cannot be sorted on.** Ordering by a hidden column leaks its values through the row order, so the permitted set decides what a heading may link on.

**`inline` does not mean every row is embedded.** It means the server produces the finished HTML for *this page of rows*: fifty rows and a link to page two, one `COUNT` and one `LIMIT`/`OFFSET`, whatever the query matches. A fifty-thousand-row table is an ordinary table. What `fetch` changes is who asks for the next page and whether the document reloads — not whether one is sent.

**Rendering is paged; `get_data` is not.** A screen draws a page; an export wants every row and calls `get_data` itself.

**A paged queryset must be ordered.** Without one the database may return rows in a different order per `LIMIT`/`OFFSET`, so a row appears on two pages and another on none. The component's `sort` decides, then the model's own `Meta.ordering`, then the primary key — never nothing.

What it does not do is what a grid library is for: dragging a column wider, re-sorting without a round trip, and editing a cell in place. Core ships the write endpoint and a server-rendered row-edit form; **inline cell editing is `table_tabulator`'s**.

**`table_tabulator`** — contrib, Tabulator, `fetch` mode. The interactive table: client-side sort and filter, remote pagination, column resize and reorder, inline cell editing.

It registers under its own key rather than replacing `table_plinta`, because the component registry refuses a duplicate by design (§7.2). A block chooses one, and a page may hold both.

**Why the split.** A grid library is an opinion about how a table behaves, and putting one in core makes every consumer either accept that opinion or fight it. The same argument that keeps a CSS framework out of core (§10.8) applies with more force here, because a table is the component most likely to be replaced: a consumer who prefers AG Grid, DataTables or their own writes a component and registers it, rather than working around Tabulator.

**The payoff is that a viewer's page loads no vendor JavaScript at all.** Layout is CSS grid from the stored position, styling is plinta's own, and the table is HTML. Core carries no front-end major-version upgrade — not one.

**`kanban_plinta`** — the largest at 1,106 LOC and 18 config keys. Shows label chips when `contrib.labels` is installed and colours columns by workflow state when `contrib.workflow` is — both declared `enhances`, each naming its substitute (§2.5).

**`pivot_webdatarocks` and `pivot_flexmonster`** — two packages, where v1 had one holding both behind `providers.py` and a setting. Flexmonster is commercial and cannot be vendored (§17), so it fetches its own assets and asks for its own licence key; WebDataRocks is free and vendors normally. Neither knows the other exists, and an installation picks by which it adds to `INSTALLED_APPS`.

**`gantt_jsgantt`** — **`critical_path` is declared and never implemented.** It appears in the config schema and a docstring listing options, and nowhere else: the key is accepted, validated and ignored. Dropped. It is one of the four findings in §21.11, and the only one where the **key itself** is the fiction — the other three document a real key wrongly.

**`chart_plotly`, `gauge_plotly`, `kpi_plinta`** — move to `inline`. A KPI is one number and currently costs a round trip to deliver it.

**`details-card`** — the strongest candidate to have stayed in core, excluded to keep ADR 0005 absolute. Core composes a detail page but renders a record as a single-row table until this is installed.

**`repeater`** — renders a child block once per group value. `component.py:150` lazily imports `plinta.blocks.services`, so **a component imports blocks: layer 6 importing layer 7**, hidden inside a function where only an AST walk would find it.

The core/contrib split resolves it rather than requiring a redesign. Core components must not import `blocks`; a **contrib** package may import any core layer, `blocks` included. Moving the repeater to contrib — which ADR 0005 does anyway — makes the import legal.

**`text`, `alert`** — 115 and 114 LOC, no vendor, no data fetching. The cheapest things in the catalogue and the least likely to break.

### 11.3 Decisions

| Item | Decision |
|---|---|
| Components in core | `table_plinta` only |
| Alias `view_config.py` files | **deleted** — one schema unless overridden |
| `_XViewSaveIn` × 5 | **deleted** — `config_key` on `ViewRouterSpec` |
| Vendor layout keys (chart, pivot) | **namespaced** under `vendor` |
| `kpi.decimal_places` | **dropped** — `DataSourceField.decimals` wins |
| `gantt.critical_path` | **dropped** — declared, never implemented |
| `chart_plotly`, `gauge_plotly`, `kpi_plinta` mode | **inline** |
| `repeater` importing `blocks` | legal once contrib; forbidden in core |
| kanban's label chips / state colours | `enhances`, each naming its substitute (§2.5) |


---

## 12. The authoring screens

Plinta ships the screens that configure plinta. They are the reason a non-developer can build a dashboard, and they are as much a deliverable as the rendering engine.

All four are ordinary permission-gated screens: `view_block`, `change_datasourcefield` and their kin decide who sees them, with no separate admin concept.

### 12.1 The Data Sources screen

Registers a model and manages its columns. One screen, two levels: a list of DataSources, and per DataSource its `DataSourceField` rows with their thirteen options (§6.2).

Creating a DataSourceField mints its field permissions; renaming one renames the codename; deleting removes them (§5.7). The screen is therefore the entry point for the permission surface as well as the column surface — which is worth knowing before changing it.

### 12.2 The Blocks catalogue

Lists every block a viewer may see, with its component type, DataSource and owner. Create, duplicate, share, delete.

### 12.3 The block inspector

Edits one block's config. It **derives its form from the component's pydantic schema** — walking `model_fields`, choosing a widget per annotation, coercing the POST back (§8.9).

**Thirteen config fields carry a hand-written editor today**, one template each under `overrides/fields/<component_type>_<field>.html`, replacing the derived widget for that one row:

| Component | Fields |
|---|---|
| `chart` | `series` |
| `gauge` | `thresholds` |
| `kanban` | `columns`, `column_labels`, `sort_fields`, `create_defaults` |
| `details-card` | `fields`, `sections`, `exclude_fields`, `field_overrides`, `value_classes` |
| `table` | `row_formats`, `create_defaults` |

They are ordinary schema fields, not extras. They resist derivation for two separate reasons, and each gets its own fix.

**The annotations carry no shape.** Every one of them is `list[dict[str, Any]]` or `dict[str, Any]`, from which the only derivable widget is a JSON textarea. **v2 types them** — `list[ChartSeries]`, `list[Threshold]`, `list[RowFormat]` — which lets the engine derive a repeating sub-form, and makes config validation validate them instead of accepting any dict (§7.2).

**Some still need a real editor.** Reordering series by drag, picking a colour, mapping a workflow state to a column: typing the schema does not produce those. So the form engine takes an **override registry** — a component declares a template for one of its config fields and the engine uses it instead of the derived widget. Without it the engine handles the simple 80% and someone hand-writes the rest again, which is how v1 arrived at thirteen templates and no place to put them.

### 12.4 The page composer

Arranges blocks on the 12-column grid — drag, resize, add, remove — driven by GridStack, persisting `PageBlock` positions.

**GridStack is an edit-mode dependency only.** The stored `column` / `row` / `width` / `height` map straight onto CSS grid (§9.3), so a viewer renders the layout with no JavaScript and never downloads the composer.

It also edits page settings: name, menu placement, type, filters.

### 12.5 Decisions

| Item | Decision |
|---|---|
| Authoring screens | **ship with plinta** — they are the product, not tooling |
| Gating | ordinary model and instance permissions; no admin concept |
| Form derivation | from the component's pydantic schema (§8.9) |
| Untyped config fields (`list[dict[str, Any]]`) | **typed sub-models**, so the engine can derive a repeating sub-form and validation is real |
| Editors typing cannot produce | an **override registry** — a component declares a template per config field |
| Grid persistence | `PageBlock` positions, GridStack-driven |
| GridStack | **edit mode only** — view mode is CSS grid |

## 13. Framework pages and seeding

Plinta ships working screens, not just the machinery to build them. A consumer runs one command and has a usable application.

### 13.1 What ships

| Screen | Type | Provided by |
|---|---|---|
| Home | shell | the shell |
| Account settings | `custom-template` | core |
| Permission console | `custom-template` | core (§5.11) |
| Capability matrix | `custom-template` | core |
| Audit log viewer | `dashboard` | `contrib.audit` |
| Workflow permissions, Permission audit | `custom-template` | core (§5.11) |
| Platform architecture | `custom-template` | core |
| Log out | `custom-template` | the shell |
| Lookups, Users | `dashboard` | core |
| Organizations, Labels, Notifications, Workflows, Reports | `dashboard` | the contrib package that owns each |

Blocks and Data Sources are **not** seeded — they are fixed sidebar links to authoring screens (§12), not `Page` rows.

### 13.2 Seeding

Nine commands: one orchestrator and eight per-app seeders. Every one is **idempotent**.

| Command | Owner in v2 | Seeds |
|---|---|---|
| `seed_platform_pages` | `pages` | menu groups, the core `custom-template` pages, then calls whichever of the rest are installed |
| `seed_lookups_page` | core | Lookups |
| `seed_users_page` | **core** — see below | Users |
| `seed_audit_page` | **`contrib.audit`** — new | the audit log viewer |
| `seed_reports_page` | **`contrib.reports`** — new | Reports |
| `seed_organizations_page` | `contrib.organization` | Company, Site, Business Unit |
| `seed_labels_page` | `contrib.labels` | Labels |
| `seed_notifications_page` | `contrib.notifications` | Notifications |
| `seed_workflows_page` | `contrib.workflow` | Workflows |

The orchestrator calls a contrib seeder only when that package is installed, which is how a minimal install seeds the core screens and nothing else.

Two are new. `seed_audit_page` takes over the viewer the orchestrator builds inline today. `seed_reports_page` replaces the hard-coded "Excel Reports" link in the v1 base template — a contrib screen reached through core chrome, which §10.2 does not allow. A contrib package's screen is a `Page` it seeds, so it appears in the menu through the same permission-filtered path as every other page and disappears when the package is uninstalled.

**A seeder belongs to the app whose screens it creates.** That keeps a package's screens with the package that can be uninstalled — uninstall `contrib.labels` and its page goes with it, rather than leaving a dead `Page` row core would have to clean up.

**The orchestrator is the current violation.** `seed_platform_pages` today builds the audit viewer inline — a seven-field DataSource, three page filters — and seeds three permission-console pages by naming `accounts` templates. The one file whose job is delegation is the one hard-coding two other apps' screens. v2 moves the audit viewer to `contrib.audit`; the permission console is core (§5.11) and stays.

**`seed_users_page` has no owner once `accounts` dissolves** (ADR 0002). Core takes it: core already registers `AUTH_USER_MODEL` as a DataSource so DSF-driven field permissions cover it, so the DataSource the page needs exists either way.

### 13.3 Seeded configuration is still configuration

These screens are `Page`, `Block` and `DataSource` rows — the same rows a user creates in the browser, with no privileged status.

**Consequence:** a consumer may edit or delete them, and re-running the seeder restores them. That is the intended behaviour, and it is why `is_system` is dropped (§9.8) — protection belongs to permissions, not to a flag that makes some rows special.

**Consequence for the config lifecycle:** `dumpconfig` (§16) exports seeded rows alongside authored ones, because there is no difference between them. A consumer who customises a shipped screen keeps that customisation in their own export.

### 13.4 Decisions

| Item | Decision |
|---|---|
| Ship working screens | **yes** — a consumer runs one command and has an application |
| Seeder ownership | the app whose screens it creates — the audit viewer moves to `contrib.audit`, the users page to core |
| Idempotency | required |
| Seeded rows | ordinary configuration, deletable, restorable, exportable |
| `is_system` protection | **dropped** — permissions, not a flag |

## 14. Contrib packages



### 14.0 What a contrib package is

Optional. Never imported by core. Installed by listing it in `INSTALLED_APPS`, and removable by not listing it.

**Every contrib package:**

- registers itself from its own `AppConfig.ready()` — components, renderers, capabilities, policies, event listeners, placeholders
- declares `requires` (core layers, checked at boot), and where applicable `enhances` or `composes` (§2)
- ships its own models, migrations, templates, static assets, front-end adapter and vendor
- ships the **skills** for whatever extension points it provides (§25)
- passes the import-boundary test: it may import any core layer, and another contrib package only where it declares `enhances` or `composes` (§2.5)

**A contrib package may import `blocks` and `pages`.** Core layers may not import each other out of order, but contrib sits above all of them — which is what makes `contrib.components.repeater` legal where a core component would not be (§11.2).

**Uninstalling is a supported state, not a degraded one.** Every package below states what stops working when it is absent, and in every case the answer is "that feature", never "the page breaks".

### 14.1 Sweep: reports

Two findings, both structural rather than cosmetic.

**`ScheduledReport` can name a report two ways.** It carries a `report_definition` FK *and* a `report_code_name` — *"Code-registry report name. Used only if `report_definition` is null."* So a report is either a database row or a code-registered function, and the schedule accommodates both.

**Decision: database definitions only.** A report is configuration — §16 makes it exportable, diffable and reviewable, which a code registry is not. A report needing computation gets it from an annotation (§6.9) or a queryset modifier (§6.4), both of which are already registered mechanisms. `report_code_name` and the code registry go, and §20's rule applies: a second mechanism for one concept is the thing to remove.

**`ReportDefinition` carries both `owner` and `is_public`,** where every other shareable expresses public as `owner IS NULL`. `is_public` is **dropped**; reports normalise onto the shareable model.

The second field exists because `owner` meant *who may edit* and `is_public` meant *who may download* — but the shareable model already expresses both, once the three verbs are available:

| State | Meaning | Mechanism |
|---|---|---|
| public | everyone views; admins edit | `owner IS NULL`, edit via `Public & HasPerm('change_reportdefinition_owner')` (§5.8) |
| private | the owner views and edits | `owner` set |
| private + **shared** | named users also view | `InstancePerm` grant |
| private + **pushed** | each recipient gets their own copy | `copy_to` per recipient |

Publishing a report therefore means giving up ownership, and public reports are maintained by whoever holds the publish permission. That is accepted, not worked around — it is the same trade every other shareable makes, and one model for all five is worth more than reports keeping a private axis.

### 14.2 Sweep: workflow, notifications, actions

**`workflow`** — transitions carry `requires_confirmation` with a message, `requires_comment`, a `permission_codename`, and presentation (`color`, `icon`, `order`). All keep: they are the vocabulary of a transition, and each is read at render or guard time. `WorkflowStateAllowed` moves here from core (§5.4).

**`notifications`** — dormant in the surveyed install: four seeded `NotificationType` rows, zero notifications, zero queued email, zero preferences. Kept regardless, because §4.9 makes it the app every other one used to reach into, and the whole event bus exists partly to serve it. What changes is direction: it subscribes rather than being called.

**`actions`** — **not a contrib package.** It is deleted from plinta and rebuilt, if ever wanted, as a consumer app. `Urgency` goes with it, taking the last domain noun out of `core`. ADR 0008 (§24) has the reasoning.

### 14.3 Sweep: `FilterSet`

Zero `FilterSet` rows, against six `PageFilter` rows — the *bar* is used, saved *values* are not. All of it stays in **core**: `SavedView` in `blocks`, `FilterSet` and `PageFilterPreference` in `pages` (§14.3a).

| Field | Decision |
|---|---|
| `name`, `description`, `values` | keep |
| `data_source` | keep — the datasource-level scope, used by reports |
| `page` (nullable) | keep — narrows a preset to one page's bar |
| `owner` | keep — `null` = public, and `is_public` is already a property over exactly that |
| `is_default` | keep — auto-load is the point of a saved preset |
| `is_active` | **drop** — a personal preset is deleted, not disabled |

#### 14.3a Personalisation is core, not contrib

ADR 0004 (§24) did two things and only one was about packaging: it moved the *merge* out of components into blocks, and it moved the *models* to contrib. The first is the layering fix and stands. The second is reversed.

**All three tests (§2) say core; only a paraphrase of one said otherwise.** The sentence test was applied as "can core render a screen without it?" — but the sentence promises *interactive* screens, and a screen that forgets the columns you chose and the filters you set is not interactive. The optionality was fiction: a dashboard product where nobody can save their column order is not a smaller product, it is a demo.

The noun test agrees and is the sharper statement of why. `SavedView` and `FilterSet` name no real-world business object; they are plinta's own machinery for remembering how someone arranged a screen — the same species as `Block` and `Page`, which are core without argument. A `Comment` or a `Company` exists in the world; a saved view does not.

The delta pattern is also one idea: a Block is a config over a Component, a `SavedView` is a delta over a Block, a `FilterSet` is values over a Page's bar. Splitting it across the boundary obscured that.

**A confirming signal.** Making it core removes a cross-contrib dependency outright — `reports enhances personalization` becomes an ordinary contrib-imports-core edge, needing no declaration, guard or system check.

**No new layer.** `SavedView` lives in `blocks` and `FilterSet` / `PageFilterPreference` in `pages` — each sits with the thing it is a delta over. The config-resolution *hook* disappears with the optionality; `blocks` merges directly.

**The component contract is untouched.** Config in, HTML out, and a component still never learns a saved view was involved.

**Two scopes, deliberately.** A FilterSet bound to a `page` holds values for that page's filter bar; one bound only to a `data_source` holds values a report can name. The four-way key `(data_source, page, name, owner)` follows from that and stays.

A FilterSet is a shareable, so it gains **share, copy and push** (§5.10) like every other one.

#### `reports` → `FilterSet` needs no declaration

`reports/builder.py:308` and `reports/views.py:158` import `FilterSet`. With `FilterSet` in core `pages` (§14.3a) that is an ordinary contrib-imports-core edge — no `enhances`, no guard, no system check.

Which leaves the design with **no `composes` relationship at all**. The declared `enhances` relationships are registered once, in §2.5. Every other cross-contrib coupling in v1 turned out to be behavioural (invert through events) or generic (never a dependency).

That is not a rule being met by luck. It is what the renderer registry and the event bus are for, and it means the boot check has nothing to fail on — which is the point of writing the check.

### 14.4 What each app gains from other sections

Decisions taken elsewhere that land on a package here. The per-app entries in §14.6 do not repeat them.

| App | Gains |
|---|---|
| `export` | the two export endpoints from `blocks` (§8.10); a `('table', 'json')` renderer for block-shaped output (§7.3); asset location as a provider property (§17) |
| `organization` | the fiscal half of `organization/utils.py` (§3.4); the fiscal **placeholder** registrations (§3.6); the account-settings org cards from `pages` (§9.7); the three scope rules from core (§5.4) |
| `audit` | create rows carry initial values in `metadata` (§21); `record_restore` deleted with the signal (§8.10) |
| `workflow` | `WorkflowStateAllowed` and its state prefetch from core `permissions` (§5.4); the validation stage from core's write pipeline, as an `object_writing` subscriber that asks whether a workflow governs the model rather than testing a base class (§23) |
| `components.*` | the whole catalogue — see **§11**, which supersedes the summary here |
| every app | registers its own matrix capability rather than `pages` doing it (§8.5) |

### 14.5 Decisions

| Item | Decision |
|---|---|
| `report_code_name` and the code registry | **dropped** — reports are configuration |
| `ReportDefinition.is_public` | **dropped** — reports normalise onto the shareable model |
| `notifications` | kept despite zero rows — it supplies a shipped screen, and §21's rule applies |
| `actions` | **not a contrib package** — deleted from plinta, rebuilt as a consumer app if wanted (ADR 0008 (§24)) |
| `reports` → `export` | **`enhances`**, substituting the HTML renderer (§7.1) |
| `workflow` → `audit` | **`enhances`** — reading transition history is a functional read no event replaces; substitutes an empty history (§14.6) |
| Contrib importing `blocks` / `pages` | **allowed** — contrib sits above every core layer |
| `components.*` entry | defers to §11 |
| `FilterSet.is_active` | **dropped** — a preset is deleted, not disabled |
| `FilterSet` two scopes (page, data_source) | **kept** — page bar values, and values a report can name |
| `reports` → `FilterSet` | **no declaration** — `FilterSet` is core (§14.3a) |

### 14.6 The packages

#### `api`

The public, machine-facing data API. Optional.

**Requires:** `datasources`, `blocks`, `permissions`.
**Listens to:** nothing.
**Emits:** nothing.

##### Ships

`APIKey` — a credential bound to a user, with a hashed secret, a label, a last-used timestamp and optional scopes. The key authentication backend. Seven generic endpoints over the DataSource registry. The OpenAPI spec and its UI.

##### Generated, not written

The endpoints are generic: `/data/`, `/data/{ds}/`, `/data/{ds}/{pk}/`, `/data/{ds}/schema/` and the write verbs. Registering a DataSource publishes it; there is no per-model API code and no second description of a model that `DataSourceField` already describes.

##### Authorisation is borrowed entirely

A key resolves to a user; `get_queryset` and `get_available_fields` do the rest. Every entry point filters — the listing by model permission, the schema by field permission, the rows by row policy — so an unprivileged caller learns no model or field names.

There is no publish flag and no field-level flag. See §15.

Writes go through the block write pipeline, so an API edit is authorised, validated, audited and notified exactly like a UI edit.

##### Degrades when absent

No machine access and no key table. The UI is unaffected — it uses the private transport, which is plain Django views and does not live here.

#### `attachments`

Files attached to any record.

**Requires:** `blocks`, `pages`, `permissions`.
**Emits:** nothing.
**Listens to:** nothing.
**Ships a component:** `attachments_section`.

##### Ships

`Attachment` — file, original name, size, content type, uploader, generic foreign key to the target, and visibility mirroring the comment model. Plus the storage-bucket registration and the `attachments_section` component.

##### Opting in

A model opts in with an `attachments` generic relation.

##### Storage

Buckets are declared in settings and registered at startup, so a deployment can route different models' files to different backends without code changes.

##### Dependencies

`Pillow` ships with this app, not with core. Image handling is an attachment concern.

##### Degrades when absent

No file attachments. The section component is unregistered; a placed block referencing it renders as an empty slot.

Page templates already guard their attachment sections on context variables that are only populated when this app is installed, so no template change is required to remove it.

#### `audit`

An immutable change log. **A pure listener** — the reference example of one.

**Requires:** `events`, `permissions`. `seed_audit_page` (§13.2) adds `datasources`, `blocks` and `pages` when it lands.
**Listens to:** `object_written`, `object_deleted`, `state_changed`.
**Emits:** nothing.

##### Ships

`AuditEntry`: **one row per write**, attached to any model by content type. Carries the action, actor, timestamp, source, the target, a stored label for it, and the diff as `{field: [before, after]}`.

**Per write, not per changed field.** The event carries `changes` whole, and splitting it into a row each loses the fact that three fields moved in *one* action — which is usually the question being asked. Querying by field is a JSON key lookup, which every database plinta supports can do.

**The label is stored beside the generic relation** because a deleted row leaves that relation dangling, and an entry that cannot say what it was about is not an audit trail. The label is what survives.

##### What is recorded

**Everything, minus an excluded set** — the inverse of opting in. A trail somebody forgot to switch on is silent, and silence is the failure that matters here, so a consumer's model is recorded unless they say otherwise.

The default exclusion is **plinta's own configuration**: `blocks`, `pages`, `datasources`. Somebody dragging a block or saving a view would otherwise bury the writes an audit exists to show. `PLINTA_AUDIT_EXCLUDE_APPS` replaces the list (§19.2).

##### Sensitive fields are redacted, not dropped

A field whose name suggests a secret is recorded as changed, with both values replaced. Dropped, the entry would say nothing changed; replaced, it says the field changed and declines to say to what — which is both true and useful.

##### Why this app is contrib

It is the app that looks least optional and is in fact the cleanest listener.

Previously it was welded into core's write path at seven call sites, because writing one row per changed field needs a pre-save baseline, and the pipeline had to snapshot before saving and diff afterwards.

It needs neither now. `object_written` carries `changes` as `{field: (before, after)}`, computed by core because **core performed the write and already knew.** Audit persists what the event hands it.

That this app reduced to a listener without widening the event vocabulary is the evidence the event model is correct. Had it needed a hook inside the pipeline, the model would have been wrong. **Built, it needed nothing added** — three receivers, and no change to any core module.

##### `object_writing` is deliberately not subscribed to

A write that has not happened is not something that happened. Recording intentions would record the ones that then failed validation, and a trail containing writes that never occurred is worse than one missing writes that did.

##### Transitions

`state_changed` is recorded as a single row with state codes in the columns and workflow specifics in `metadata` — schema-pure, so audit never references a `Workflow` model and the two apps stay independent.

##### Failure policy

A failed audit write is logged and swallowed. Losing an audit row is bad; failing a user's save because of one is worse. `send_robust` would swallow it in any case (§4.7), so the log is what makes a broken listener visible rather than silent.

##### Subscriptions carry a `dispatch_uid`

So connecting twice is harmless — `ready()` can run more than once — and so a bulk import can `disconnect()` rather than write a million entries.

**A uid must be matched to remove it.** Django looks a uid-registered receiver up by uid alone, so `disconnect(the_function)` removes nothing and returns as though it worked. The package exposes `connect()` and `disconnect()` for that reason rather than leaving callers to pair them.

##### The screen is a Page, not a view

An audit log is rows with filters, which is what a page of blocks is for — so `seed_audit_page` creates a DataSource over `AuditEntry`, a `table_plinta` block and a Page, and the trail appears in the menu through the ordinary permission-filtered path (§9.5).

That it needs no bespoke screen is the point: the app registers its model and plinta draws it, the same as a consumer's own.

##### Degrades when absent

No change history, and the page goes with the app rather than leaving a dead menu entry. Nothing else changes: no core behaviour, and no other contrib app, depends on audit being installed.

#### `checklist`

Task checklists attached to any record.

**Requires:** `blocks`, `pages`, `permissions`.
**Listens to:** nothing.
**Emits:** nothing.

##### Ships

`ChecklistItem` — text, done flag, order, created-by, completed-by, generic foreign key to the target. Plus the checklist section partial.

##### Opting in

A model opts in with a `checklist_items` generic relation.

##### Note

This is the most self-contained package in the project: nothing imports it, nothing depends on it, and no migration anywhere references it. It is the shape every contrib package should aspire to, and a useful smoke test — if the import-boundary test ever reports an inbound reference to `checklist`, something has gone wrong elsewhere.

##### Degrades when absent

No checklists. Nothing else observes its absence.

#### `comments`

Threaded discussion attached to any record.

**Requires:** `blocks`, `pages`, `permissions`, `events`.
**Emits:** `comment_posted`.
**Listens to:** nothing.
**Ships a component:** `comments_section`.

##### Ships

`Comment` — body (rich text), author, generic foreign key to the target, soft delete, edited-at. Visibility mirrors the sharing model: an owner-less comment is public; otherwise it is visible to named users and groups.

The `comments_section` component ships **with this app**, registered from its own `AppConfig.ready()`. Core never enumerates it.

##### Opting in

A model opts in with a `comments` generic relation. The capability probe finds it and the section becomes available on that model's detail pages.

**Opting in makes the app required for whoever opted in.** A `GenericRelation("plinta_comments.Comment")` names a model, so Django cannot resolve it with the app uninstalled — the consumer's own model stops working, not just the section.

That does not contradict "degrades when absent" (§2.5), and the distinction is worth stating exactly:

| | with `comments` uninstalled |
|---|---|
| a consumer who never opted in | everything works; the section is simply absent |
| a block naming `comments_section` | an empty slot |
| a consumer whose model declares the relation | **their model does not load** |

So the app is optional to plinta and not optional to a model that opted in — which is what a `GenericRelation` means, and is the reason it counts as a **generic** coupling on plinta's side and a real dependency on the consumer's. A consumer who wants comments to be removable declares the relation in a separate app they can uninstall together, or drops the relation and lets the probe find nothing.

##### Mentions

Mentions are extracted from the body at post time and carried on the emitted `comment_posted` event. This app resolves who was mentioned; it does not decide what happens next.

The alternative — calling a notification app from here — is what makes that app mandatory for anybody who wants comments. This one emits and stops.

**An edit emits nothing.** A correction is not a new remark, and announcing one would notify a thread every time somebody fixed a typo.

**Withdrawing keeps the row.** A thread with a hole in it reads as a bug, and a reply answering a vanished remark reads as nonsense, so the shape of the conversation survives what was said.

**A mention that matches nobody is ignored.** A typo is not an error: refusing to post the comment is a worse answer than nobody being told.

##### Where the line falls between this app and its consumer

Some of the above are the platform's to decide and some are not, and the test is whether getting it wrong is a **defect** or a **preference**.

| | whose | why |
|---|---|---|
| commenting needs sight of the row | the app's | otherwise it is a way of reading a record you may not read |
| an owner-less comment is public | the app's | it is the permission model, and half of it cannot live elsewhere |
| a mention matching nobody is ignored | the app's | robustness; the alternative refuses a valid comment |
| **how deep a thread is drawn** | **the consumer's** | a display choice, and capping it in the model loses what somebody meant |
| whether an edit is announced | the app's, for now | announcing corrections is noise by default; a consumer wanting it subscribes to `object_written` on `Comment` |

**Replies nest to any depth.** The model stores what was sent — a reply may reply to a reply — and `depth()` tells whoever draws it how far in a comment sits. Collapsing a reply's parent at write time would silently move a remark somebody aimed at a particular one, and a limit belongs where the drawing happens.

##### Dependencies

`django-ckeditor-5` ships with this app, not with core. Rich-text editing is a comment feature, not a platform feature.

##### Degrades when absent

No comment threads, and the `comments_section` component is unregistered — a block referencing it renders as an empty slot rather than failing the page.

#### `components.*`

**See §11 — the component catalogue supersedes this summary.** Retained here only for the dependency declaration.

**Requires:** `components`, `datasources`, `renderers`, `permissions`.
**Enhances:** `kanban_plinta` on `contrib.labels` and `contrib.workflow` (§2.5). No other component declares one.
**Emits:** nothing.
**Listens to:** nothing.
**Registers:** itself, via `register_component`, from its own `AppConfig.ready()`.

##### The packages

| Package | Renders | Vendor |
|---|---|---|
| `components.table_tabulator` | an interactive table — client sort, remote paging, inline cell editing | Tabulator |
| `components.details_card_plinta` | one record as a field list | — |
| `components.text_plinta` | markdown / rich text | — |
| `components.alert_plinta` | a conditional banner | — |
| `components.kpi_plinta` | a single aggregate figure | — |
| `components.gauge_plotly` | a bounded measure | Plotly |
| `components.chart_plotly` | line, bar, area, scatter | Plotly |
| `components.pivot_webdatarocks` | cross-tabulation | WebDataRocks |
| `components.pivot_flexmonster` | cross-tabulation, licensed | Flexmonster |
| `components.kanban_plinta` | cards in state columns | — |
| `components.gantt_jsgantt` | a schedule | jsGantt |
| `components.repeater_plinta` | a repeated sub-template | — |

Named `capability_implementation` throughout (§11), so a second vendor for any
of them is a new package rather than a setting inside an existing one.

Each ships its own config schema, template, static assets and API router.

##### Why bundled components are contrib

"Add a component" is the extension anybody would realistically write, including this project. If the bundled ones had a private path into the registry and third parties had a public one, only the private path would stay working.

So every component here registers exactly the way an external package would. The contract is dogfooded by construction.

##### Vendor isolation

A component's front-end dependency ships with it, and the package name says which — Plotly with `chart_plotly`, jsGantt with `gantt_jsgantt`, Tabulator with `table_tabulator`. Core carries no CSS framework (§10.8) and no grid library (§11.2), so it absorbs no front-end major-version upgrade at all.

##### Enhancement

`kanban_plinta` shows label chips when `contrib.labels` is installed, and builds its columns from workflow states — with drag-to-transition — when `contrib.workflow` is. Both are declared `enhances`, each naming its substitute (§2.5): a card without chips, and columns grouped by an ordinary field with no transitions. The board renders either way.

##### Degrades when absent

A Block referencing an uninstalled component type renders as an **empty slot**. This is a normal state, not an error — a page must not break because a component was removed, exactly as it does not break when a viewer lacks permission on a placed block.

#### `export`

Non-HTML output formats and the endpoint that serves them.

**Requires:** `renderers`, `blocks`, `permissions`.
**Emits:** nothing.
**Listens to:** nothing.
**Registers:** the `excel`, `pdf` and `email` renderers; the export endpoint.

##### Ships

Excel (`openpyxl`), PDF (`weasyprint`) and email-HTML renderers, plus `/blocks/<name>/export/`.

##### Why export is not core

Dependency weight. `openpyxl`, `pandas` and `weasyprint` are the heaviest dependencies in the project, and `weasyprint` needs GTK native libraries — the single most awkward install in the stack.

None of them is required to render a screen. Moving them here reduces core's install to Django, django-ninja and pydantic: nothing native, nothing heavy.

Optional extras: `pdf` pulls `weasyprint`; the Excel path pulls `openpyxl` and `pandas`.

##### Permissions

An export is a bulk read and is gated as one. It goes through `datasources` with the requesting user like any other read, so it returns exactly the rows and columns that user could see on screen.

Export must never be a way around field-level permissions. A renderer cannot widen access because it never queries — it receives rows and fields already narrowed.

##### Degrades when absent

No downloads. The export endpoint is not mounted, and export buttons are hidden. Core stops knowing that export exists.

Previously core's block API imported the Excel builder and core's URL configuration unconditionally included the reports URLs, so removing export broke the boot.

#### `labels`

Categorised tags attachable to any record.

**Requires:** `blocks`, `pages`, `permissions`, `events`, `datasources`.
**Emits:** nothing.
**Listens to:** `object_written`.
**Ships a component:** `labels_section`.

##### Ships

`LabelCategory`, `Label` (name, colour, category), `LabeledItem` (the generic join), the label picker, and the `labels_section` component.

##### Opting in

A model opts in with a `labeled_items` generic relation. A DataSource exposes labels as a column by declaring a `labeled_items` field, which renders as chips.

##### Label sync on write

When a write includes a label field, this app applies the change — by subscribing to `object_written`, not by being called from the write pipeline.

Previously core's pipeline imported `LabeledItem` directly, and the kanban component imported it at module scope, which made labels mandatory for anyone wanting a kanban.

##### Enhancement relationship

`contrib.components.kanban` shows label chips on cards **when this app is installed**. Declared `enhances`, with the substitute named: a card rendered without chips (§2.5). The board is unaffected, and a missing `labels` is an informational system check rather than an error.

The awareness is one-directional — labels knows nothing about kanban — and the relationship is registered in §2.5 like every other.

##### Degrades when absent

No tagging. Label columns on a DataSource resolve to nothing; the `labels_section` component is unregistered and renders as an empty slot. Kanban cards render without chips.

#### `notifications`

In-app notifications and queued email. A pure listener.

**Requires:** `events`, `permissions`, `datasources`, `blocks`, `pages`.
**Listens to:** `object_written`, `state_changed`, `comment_posted`.
**Emits:** nothing.

##### Ships

`NotificationType`, `Notification`, `EmailQueue`, `NotificationPreference`, the bell badge and dropdown, preference UI, and a `send_queued_email` command.

##### Subscription model

A consumer registers interest per model label and event, declaring who should be notified and under what condition. Recipients are resolved from the object — owner, assignee, followers, mentioned users — and filtered by each recipient's preferences.

**A registration, not a table of rules.** Rules edited in a browser would make "who gets told" a validation surface, and a stored `{obj.owner.email}` a path from configuration into attribute traversal. `title`, `body` and `url` are a plain string or a **callable** for the same reason — never a format template.

**An event outside the vocabulary is refused at registration.** One naming an event core does not emit would simply never fire, which reads as a bug in whatever it was watching rather than in the subscription.

**`written` exists beside `created` and `updated`.** `object_written` carries `mode`, so one signal answers all three names and a subscription meaning "whenever this is touched" registers once.

**The actor is not notified by default.** Telling somebody what they have just done is the commonest complaint about a notification system; `notify_actor=True` asks for it.

##### A channel is registered too

**Where a notification goes is a second registry.** Two ship — the in-app list and the email queue — and a third party adds Discord, Slack, SMS or a webhook by registering one, not by changing this app. Both built-ins go through `register_channel` themselves, so there is no private path for them to keep working on when the public one rots.

A channel is a name, a `deliver` callable, and an optional `available` probe: somebody with no address is not offered email however enthusiastically they opted in.

**Delivering must not block.** A channel runs inside the write that caused the notification, so one that talks to an HTTP API enqueues rather than posts — `email` is the worked example, and it queues.

**A preference is per kind *and* per channel.** A column each would mean a package adding Discord adding a column here, and would stop a person taking a kind by one route and not another.

**Three answers, most specific first:** what the person said, then what the subscription defaults to for that kind, then what the channel defaults to. So a newly registered kind works before anybody has a preference row, and a newly installed channel does not switch itself on for everyone. In-app is on by default and email is off — a fresh install that mails everybody is a fresh install nobody keeps.

Email is queued, never sent inline. Delivery is a scheduled command, so a mail server outage cannot fail a save, and a message stops being retried after a bounded number of attempts: a queue that retries for ever is a queue that never drains.

##### Why this is the app that proves the rule

Every sideways dependency in the previous design pointed here: comments called it, actions called it, the workflow mixin called it, the write pipeline called it. Four contrib apps and one core module all reached into it directly, which is what made it effectively mandatory.

All four are now emitters of core signals that this app subscribes to. Nothing imports it. It can be absent and every one of those paths still runs.

##### The screens

Three, and none of them a `Page`: a bell, a list and a preference grid are views rather than compositions, so they are reached by a registered topbar item and a registered shell link (§10.2).

**The preference grid takes both axes from their registries** — kinds down, channels across. A package adding a channel adds a column and one adding a subscription adds a row, and neither touches the view.

**A channel the viewer cannot use is not offered.** No address, no email column: an unusable checkbox is a lie about what will happen.

**An unticked box is a stored `no`**, not an absent row. Left absent, the default would drift back the next time it changed.

**The bell counts what is unread and says nothing when there is none.** A zero badge is noise. It reads its count from a template tag rather than a context processor, so a screen that never draws the bell pays no query for it.

##### Failure policy

A failing handler is logged and swallowed. A notification is never worth failing a user's write for — and that covers a consumer's own callables too: a `recipients` that raises tells nobody, a `when` that raises declines, and the write succeeds either way.

##### Degrades when absent

No notifications and no email. Comments still post, transitions still execute, writes still succeed. Nothing else observes its absence.

#### `organization`

Multi-entity structure and the tenancy scoping built on it.

**Requires:** `permissions`, `datasources`, `dates`, `blocks`, `pages`.
**Emits:** nothing.
**Listens to:** nothing.
**Registers:** scope-provider policies; fiscal named-ranges into `dates`.

##### Ships

`Company`, `Site`, `BusinessUnit`, `BusinessUnitType`, `CompanyBusinessUnit`, `Currency`, the fiscal calendar, and the user grants `UserCompanyAccess` / `UserBusinessUnitAccess`.

##### Scope provider

Binds core's `FieldInUserSet` rule to the concrete hierarchy: a row whose `site` (or `company`, or `business_unit`) is not among the user's grants is invisible, in querysets and in instance checks alike.

Core's permission engine never imports this app. A project whose tenancy is a `Portfolio`, a `Desk` or a `Household` writes its own provider instead and gets identical behaviour — this app is one provider, not the provider.

##### Fiscal calendar

A fiscal year belongs to a legal entity, so it belongs here rather than in core `dates`. The app registers its named ranges into core's resolver, and fiscal options appear in filter UIs only when it is installed.

##### Degrades when absent

No tenancy scoping — ownership, public/private, sharing and field-level permissions all still apply. No fiscal ranges in filters; calendar ranges are unaffected.

Core has no notion of a company or a tenant, so a single-tenant project should not install this app. Previously it was foundational by accident: four core modules imported its date helpers at module scope.

##### Note

The user grants live here, not with the user model. They are organisation concepts that happen to reference a user; plinta does not own the user model.

#### `reports`

Defined, schedulable reports over registered DataSources.

**Requires:** `datasources`, `blocks`, `pages`, `permissions`. `pages` because a sheet may name a `FilterSet` (§14.3a).
**Enhances:** `contrib.export`, with the HTML renderer as the substitute (§7.1).
**Emits:** nothing.
**Listens to:** nothing.

##### Ships

`ReportDefinition` — a saved specification: DataSource, columns, filters, grouping, sort, output format. `ScheduledReport` — a definition plus a cadence and a recipient list. Plus the report builder, the report views, `send_scheduled_reports`, and `seed_reports_page`, which creates its own screen (§13.2).

##### Relationship to export

A report's usual output is a spreadsheet or a PDF, but `reports` does not import `export` and does not check whether it is installed. It asks the renderer registry for a format and gets back the registered renderer or the HTML one (§7.1).

So the relationship is **`enhances`**, not `composes`: without `export` a report definition still exists, still validates, still lists, still runs — to screen. Install `export` and the same definition produces a file. That is the whole reason the registry substitutes instead of raising.

`ScheduledReport` degrades the same way: the email sends with an HTML body instead of an attachment. `django.core.mail` is Django's, so delivery never depended on `export` in the first place.

##### Permissions

A report runs as a user and returns what that user could see. A scheduled report runs as its owner; recipients receive that owner's view of the data.

This is deliberate and must be stated to whoever schedules one: a scheduled report can deliver rows a recipient could not fetch themselves. It is the only place in plinta where data reaches someone outside their own access scope, and it is why scheduling is an owner-level act.

##### Degrades when absent

No report definitions, no scheduled delivery. Ad-hoc block export is unaffected — that belongs to `export`.

#### `workflow`

A database-backed state machine for a consumer's models.

**Requires:** `permissions`, `events`. An admin screen adds more and arrives as a seeder, the way audit's page does — the state machine itself needs neither `blocks` nor `pages`.
**Enhances:** `contrib.audit` — an empty history is the substitute; see below.
**Emits:** `state_changed`.
**Listens to:** nothing.

##### Ships

`Workflow`, `WorkflowState`, `WorkflowTransition` — and **no base class**.

States and transitions are data, not code: a transition carries a from-state, a to-state, an order, an optional confirmation requirement and an optional guard.

##### Registration, not inheritance

**A consumer declares its own field and says so.**

```python
class Order(models.Model):
    state = models.CharField(max_length=40, blank=True)   # their column

Workflow.objects.create(content_type=..., state_field="state")
```

A mixin would put two foreign keys to this app's tables on the consumer's model, which makes the app **required** for whoever opted in — the same trap a `GenericRelation` sets for `comments` — and contradicts the promise that models stay plain Django.

**And the state stays an ordinary column**, so it sorts, filters and groups like any other. A foreign key to a state table sorts by row id unless every screen remembers to traverse to an order field, which is the kind of thing screens forget.

**The price is one call.** Nothing here can hook a save on a model it does not own, so a consumer creating a row calls `set_initial(obj)` to put it in its starting state. That is the honest cost of not owning the model, and it is a line rather than a base class.

##### The three gates

Every move passes all three, and they answer different questions.

| Gate | About | Refuses when |
|---|---|---|
| the transition's **permission** | the person | they do not hold `transition_order_open_to_closed` |
| the **row policy**, via `can(user, "change", obj)` | their reach | the row is not theirs to change |
| the **guard**, when the transition names one | the row | "this order still has open lines" |

They are separate because no grant can express a condition about a row, and no condition should decide who is allowed.

**A guard is registered by name**, never a stored dotted path, so a transition row cannot name arbitrary importable code. It returns `True`, `False`, or a **string** — the reason, which is what a screen shows instead of a button that silently does nothing.

**A guard that raises refuses.** Permitting on error would wave through the move the condition was written to stop.

##### One permission per transition, renamed in place

`transition_order_open_to_closed` is grantable on its own, so "may move an order to closed" is separable from "may edit an order" — which is the whole reason a transition carries a permission rather than reusing `change_*`.

Minted when the transition is saved, removed when it is deleted, and **renamed in place when a state's code changes** — including every other transition that mentions that state. A grant points at a permission's primary key, so recreating one drops every grant on it silently; this is the same treatment a column's permission gets, for the same reason.

`rebuild` is the idempotent backstop, for an import that used `bulk_create` and fired no `post_save` at all.

##### What a screen is offered

`available(obj, user)` returns every move out of the current state, **including the refused ones and why**. A move that vanishes reads as a missing feature; one greyed out with "you do not have permission to make this move" reads as a permission to ask for.

##### The screens

**A capability, not a component.** The status panel is about *one record* and hangs off a detail page; a component draws rows. It says where the row is, offers the moves, and shows the history behind a fold.

**Which models are governed is read from the rows**, not from a registry in code — a workflow is data, so the question belongs to the database. Deactivating one removes the panel.

**A refused move is drawn greyed with its reason in the title**, which is what makes `available` returning refusals useful rather than merely honest.

**A transition is a POST.** A move is a write, and a write behind a GET is a link a crawler can follow. The row is found through the workflow's own content type rather than trusted from the request, so a caller cannot name a transition on one model and a row on another.

**A state renders as a chip through a registered field renderer**, so a table column shows "In review" rather than `review`, in whatever class the state declares. The colour is a class name, so core's tokens draw it and this app names no palette. A code nothing describes still shows — a state removed from a workflow leaves rows holding it, and the code is more useful than nothing.

##### Guards

A transition is permitted when the actor holds its declared permission and the model's instance policy admits the object. Transition permissions are generated per transition, so "may move Open → In Progress" is grantable independently of "may edit".

Execution is atomic: the state change and its emitted event either both happen or neither does.

##### Emits, rather than notifies

On a completed transition the app emits `state_changed` with **string state codes** and a `metadata` dict carrying workflow specifics. Schema-pure, so a listener never imports this app to read one.

It calls neither audit nor notifications. Both subscribe.

**The move is atomic and the event follows the save**, so a listener reading the object sees where it now is rather than where it was.

##### Reading the transition history

The other half does not dissolve: rendering where a row has been is a **functional read**, and no event delivers history to whoever asks for it.

So `workflow` declares **`enhances: audit`** and names its substitute. `history(obj)` reads the audit trail — which records `state_changed` like any other write, so this app needs no history table of its own — behind a check that the app is installed. With it absent the call returns nothing and a panel says so. The state machine is unaffected; only the record of where a row has been is missing, which is exactly what audit is.

The import is inside the function rather than at module scope, and a test asserts that: an `enhances` reached at import time is a dependency wearing a different word.

##### Degrades when absent

A consumer keeps their state column — it was always theirs — and it stops moving. Nothing in core references a workflow state, and a component colouring rows by one binds to a column that is simply no longer changed by anything.

A consumer with its own state machine can emit `state_changed` directly and get audit and notification coverage without installing this app.

---

---

# Part IV — Cross-cutting

## 15. The API

Plinta has **two API surfaces** with different contracts. Conflating them is how a platform loses the ability to change its own frontend.

| | Public data API | Private UI transport |
|---|---|---|
| Audience | machines, partners, scripts | plinta's own frontend |
| Shape | resource-shaped JSON | HTML fragments and widget-shaped JSON |
| Framework | django-ninja | plain Django views |
| Auth | API key, or session | session |
| Auth failure | `401` | redirect to login |
| Versioned | yes | no |
| In the OpenAPI spec | entirely | not at all |
| Stability | a promise | none — changes with the UI |

### 15.1 Public data API

#### Generated from the DataSource registry

A `DataSourceField` already records the field path, label, type, filterability and lookup. That is a serializer definition. The API is generated from it, so there is no per-model API code and no second description of the same model.

```
GET    /api/v1/data/                      datasources you may view
GET    /api/v1/data/{ds}/schema/          fields you may see
GET    /api/v1/data/{ds}/                 rows you may see
GET    /api/v1/data/{ds}/{pk}/
POST   /api/v1/data/{ds}/
PATCH  /api/v1/data/{ds}/{pk}/
DELETE /api/v1/data/{ds}/{pk}/
```

Seven handlers in total — not seven per model. Registering a DataSource publishes it; no further step.

#### Permissions are the only gate

There is no field-level API flag, and a DataSource is published only when `show_in_api` is set (**revised** — see §6.1a; it is curation, not access control). `view_{model}` and `view_{model}_{field}` answer both questions already, and a second mechanism answering the same question is a mechanism that drifts.

**Every entry point filters, not just the row fetch.** This is what makes the absence of a flag safe:

| Endpoint | Filtered by |
|---|---|
| `/data/` | model permission — an unprivileged caller gets an empty list, learning no model or field names |
| `/data/{ds}/schema/` | `get_available_fields(ds, user)` |
| `/data/{ds}/` | `get_queryset(ds, user)` |

The listing is permission-filtered for the same reason the menu is: discovery must not reveal what access denies. A static spec enumerating every resource would leak exactly the map the filtered listing withholds, so the spec is either generated per identity or kept structural (`/data/{datasource}/`), with `/data/` as the discovery mechanism.

Precedent: Frappe exposes every DocType and Directus every collection, both gated purely by permissions.

#### Reads and writes reuse the existing paths

```python
@router.get("/data/{ds_name}/")
def list_rows(request, ds_name: str, q: QueryParams = Query(...)):
    ds = get_datasource(ds_name)
    fields = get_available_fields(ds, request.user)
    qs = get_queryset(ds, request.user)
    qs = apply_filters(qs, q.filters, fields)
    qs = apply_ordering(qs, q.order, fields)
    return paginate(qs, q.page, q.size, fields)
```

No model names, no serializers, no access checks of its own — the narrowing happens inside the two `datasources` services, so the API is structurally incapable of returning what the UI would hide.

Writes go through the **block write pipeline**: same authorisation, same model validation, same `object_written` event. An API edit is therefore audited and notified exactly like a UI edit, with no extra code.

#### API keys authenticate as a user

A key resolves to a user. Row policies, field permissions, sharing and tenancy then apply unchanged.

**There is no parallel authorisation model for the API.** A key is a credential, not a permission system. Scopes, where used, narrow a key *below* what its user may do and never above.

Per-key field visibility needs no feature: mint the key against a service user whose role lacks the field permission.

#### Pagination and limits

Every list response is paginated with a hard maximum page size. Permissions decide what a caller may read; page caps and rate limits decide how fast — browsing and bulk extraction differ in economics, not in authorisation.

#### Getting the screen rather than the model — in short

A caller wanting a table exactly as it appears — the block's columns, in order, with the viewer's saved view applied — uses the **export path**, not this API: `/blocks/<name>/export/?format=json`, served by a registered `('table', 'json')` renderer. The full treatment, and why unifying the two would freeze the UI behind a version guarantee, is §7.3.

The two are separate because they name different things: `/api/v1/data/instruments/` is *the Instrument resource*; block-shaped output is *this screen*. Shape follows the block, so editing a block changes that payload — the operator's call, and the operator's consequence.

A saved **filter** is different: it is values, not shape, so it belongs here. The caller expands it — publish `FilterSet` (`show_in_api`), read its `values`, pass them as filters. No server-side `?filterset=` parameter, and therefore no fourth registry. See §6.3.

#### Where it lives

`contrib.api`. A machine-to-machine API is not required to turn models into screens, so it fails the sentence test. A project that does not want one does not mount it and does not carry the key table.

### 15.2 Each surface uses its framework's shape

**The public API returns what django-ninja returns.** A resource on 200, and ninja's own `{"detail": [...]}` on 422 for a validation failure. No envelope, and no `NinjaValidationError` override to impose one.

v1 wrapped every response in `{"success": …}` and overrode ninja's error handler so validation failures matched. That is fighting the framework for a contract it already has — and the OpenAPI spec then documents a shape ninja did not generate, so the two drift.

**The private transport uses the envelope** (§3.1), because nothing else gives it one. Plain Django views have no response convention, one client consumes all of them, and `{"success": true|false}` is simpler for that client than branching on status across forty-odd endpoints.

| | Public API | Private transport |
|---|---|---|
| Success | `200` + the resource | `{"success": true, "data": …}` |
| Failure | `422` + `{"detail": […]}` | `{"success": false, "errors": {field: […]}}` |
| Body parsed by | ninja, from `body: Schema` | `parse_request` |
| Specified | OpenAPI | not at all |

Two surfaces with two contracts is ADR 0007 (§24) applied rather than restated. The consequence is that `EnvelopeOK` and `EnvelopeError` are deleted: they were pydantic models nothing ever constructed, declared so ninja could document the envelope — and ninja no longer serves one.

### 15.3 One content type for writes

**A write endpoint accepts `application/json`. Another content type is a 415, not a second parser.**

The exception is file upload, which is `multipart/form-data` because a file cannot travel as JSON without base64. `contrib.attachments` owns the only such endpoint.

This is already paid for: the vendored **`json-enc`** htmx extension (§17) makes plinta's own forms submit JSON, and the shared client (§7.4) builds every other request. Nothing on the wire is form-encoded.

The rule exists because v1's write endpoints branched on `request.content_type` and the two branches had different contracts. The JSON branch validated with pydantic; the form branch hand-rolled it, so `page_size=abc` raised `ValueError` and `columns={` raised `JSONDecodeError` — 500s where the JSON branch returned a 400, and unknown fields silently accepted where the JSON branch rejected them. One validated path and one unvalidated one, selected by a header.

### 15.4 Private UI transport

Plain Django views, per app, with normal URLconfs and `@login_required`.

```python
@login_required
def block_rows(request, name):
    return HttpResponse(render_block(get_block(name), request.user))
```

Fragments are not in the OpenAPI framework, so they are not in the spec, carry no version and promise no stability. They change whenever the UI changes.

The same applies to the **widget data feed** — the JSON a table or kanban fetches. It is block-scoped, shaped by that block's columns, filters and the viewer's saved view, and it is deliberately *not* the public API: unifying them would leak block knowledge into the public contract and freeze the UI's payload behind a version guarantee. Both go through the same `datasources` services underneath, which is the part that should be shared. See §6.3.

#### Why fragments left ninja

In the previous design 46 of 81 endpoints were HTML fragments marked `include_in_schema=False`, so the published spec described 43% of the surface. Read shapes were pinned to frontend widgets — Tabulator, TomSelect, htmx — and documented as such.

The concrete cost was an auth workaround. Ninja owning a fragment path answers an unauthenticated request with `401 {"detail": …}`, which HTMX then swaps into the page. The only escape was `auth=None` on `notifications/preferences/`, which made that endpoint's safety depend on the *consuming project's* `LoginRequiredMiddleware`.

A library must not depend on a consumer's middleware for its own authentication. `@login_required` redirects, which is what a browser wants, and the workaround disappears.

This is not a new routing system: `plinta/urls.py` already existed as a `reverse()` shim marked for deprecation. It stops being deprecated and gets the job it is good at.

#### The cost

`reverse()` splits across namespaces — `api:` for JSON, per-app namespaces for fragments. That is the one real papercut, and it is accepted.

### 15.5 Versioning

The public API owns its path prefix and its version together; a library must not declare a version whose path a consumer chooses. Breaking changes to a published resource require a new version, not an edit.

The private transport is unversioned by definition.

## 16. Configuration lifecycle

Screens are database rows. That is what makes plinta pleasant — a page is rearranged in a browser, not in a deployment — and it creates one problem: configuration built in a browser has no history, no diff, no review and no path from one environment to another.

This is the answer to that problem.

### 16.1 Three kinds of row

The lifecycle depends entirely on telling them apart.

| Kind | Rows | Owner | Travels between environments |
|---|---|---|---|
| **Configuration** | DataSource, DataSourceField, Block, Page, PageBlock, PageFilter, MenuSection, MenuGroup | none (public) | **Yes** — it is a deliverable |
| **Personalisation** | SavedView, FilterSet, PageFilterPreference, owned Blocks and Pages | a user | No — it is that user's, in that database |
| **Data** | everything a consumer's models hold, plus comments, labels, attachments, audit | — | No |

**Ownership is the line.** An owner-less row is shared configuration and is exportable. An owned row belongs to a person and stays where it is. This needs no new flag — plinta already treats `owner is null` as public.

### 16.2 `dumpconfig` and `loadconfig`

Two management commands.

`plinta dumpconfig [--page slug …] > config/screens.yaml` serialises the configuration graph to human-readable, diffable YAML: DataSources with their fields, Blocks with their configs, Pages with their blocks, positions and filters.

`plinta loadconfig config/screens.yaml` applies it as an idempotent upsert.

The export is **committed to the consuming project's repository**. A dashboard change then arrives as a reviewable diff in a pull request, and production is updated by applying a file rather than by rebuilding a screen by hand.

### 16.3 Natural keys, never primary keys

Primary keys differ across databases, so the export is keyed by identity that does not:

| Model | Key |
|---|---|
| `DataSource` | `app_label.model` of its content type |
| `DataSourceField` | data source + field path |
| `Block` | name (unique among public blocks) |
| `Page` | slug (unique among public pages) |
| `PageBlock` | page + block |
| `PageFilter` | page + field path |
| `MenuSection`, `MenuGroup` | name — a page's menu placement is meaningless without them |

A referenced component type that is not installed is exported as written and imported as written. Configuration outlives the packages that render it, exactly as an empty slot outlives an uninstalled component.

### 16.4 Import semantics

- **Upsert by natural key.** Matched rows are updated, unmatched rows created.
- **Never deletes** unless `--prune` is passed, which removes public configuration absent from the file. Off by default: an accidental prune destroys screens.
- **Never touches owned rows.** Someone's saved view is not collateral in a deployment.
- **Atomic.** The whole file applies or none of it does.
- **Validated before writing.** Block configs are checked against their component's schema, so a bad config fails the import rather than the page.

### 16.5 Drift detection

`plinta dumpconfig --check` exits non-zero when the database holds public configuration that differs from the committed file — the same shape as `makemigrations --check`, and suitable for CI.

This is what stops the file from silently rotting the moment someone edits a dashboard in production.

### 16.6 What this deliberately does not do

**It is not a seeder.** Configuration is authored in the UI; the file is generated from the database, never hand-written. Committing seeder code produces two sources of truth that diverge, and the code eventually clobbers the UI edits.

**It does not make the file the source of truth.** The database remains authoritative at runtime. The file is a snapshot for review and transport.

**It does not version screens.** Rolling back a dashboard means reapplying an earlier file from git history — the repository is the history, and plinta stores no revisions of its own.

## 17. Assets and theming

**Decided.** Assets are served from `static/`, not fetched from a CDN at runtime. There is no bundler, no `package.json`, no node in the toolchain.

**The precedent already exists:** v1 serves its vendored libraries from `static/plinta/vendor/`. This extends that to everything that can follow it.

### 17.1 Why not a CDN

The deployment documentation already records the cost: an offline or strict-CSP deployment must vendor the CDN scripts by hand and patch the base template. Vendoring inverts that — the default works offline and under a strict CSP, and no deployment depends on a third party being reachable.

### 17.2 Why not a build step

A bundler would buy npm packages, TypeScript over 4,227 lines of untyped JS, and tree-shaking. It would cost a second ecosystem: a lockfile, transitive dependencies, audit noise, bundler major versions, and build failure as a new class of release problem.

Since plinta is pip-installed, a build could only ever run at **release time in CI**, shipping compiled assets in the wheel — a consumer must never be asked to run npm. That is workable, and still a larger upgrade tax than the one it removes.

**TypeScript is the genuine loss** and the strongest argument for building. It is deferred, not foreclosed: nothing here prevents adding a bundler once the JS settles into "one client, N adapters" and it is clear what would be compiled.

### 17.3 Where each vendor lands

| Vendor | Used by | Lands |
|---|---|---|
| Bootstrap Icons | core chrome | vendor — the icon set alone; core ships no CSS framework (§10.8) |
| htmx + `json-enc` | core transport | vendor |
| Tabulator | `table_tabulator` (contrib) | vendor, with the component |
| Tom Select | pickers (core) | vendor |
| Luxon | date handling (core) | vendor |
| GridStack | the page composer (core) | vendor — loaded in edit mode only |
| Plotly | `contrib.components.chart` | vendor **with that package** |
| WebDataRocks | `contrib.components.pivot` | vendor, licence permitting |
| Flexmonster | `contrib.components.pivot` | **cannot be vendored** — see below |

A component's vendor ships with the component, so core carries chrome and nothing else (ADR 0005 (§24)).

### 17.4 Two constraints that shape it

**Licensing.** Flexmonster is commercial and requires a licence key. Loading it from their CDN is use under their terms; **redistributing it inside an MIT-licensed wheel is not.** It therefore stays remote, or is supplied by the consumer. WebDataRocks is free but proprietary, so its terms must be checked before vendoring rather than assumed.

The pivot provider abstraction already accommodates this: `components/pivots/providers.py` declares each provider's `css` and `js` lists, so a provider may point at local files or remote ones. **Asset location becomes a provider property**, not a global rule — which is the only design that survives a vendor that cannot be shipped.

**Size.** Plotly is several megabytes minified. It travels with `contrib.components.chart`, so core stays small and a consumer who never installs charts never pays for it — but the wheel for that package will be large, and that is a deliberate trade rather than an oversight.

### 17.5 Upgrades

Vendored assets do not update themselves, which is the real cost of this choice. So:

- a **manifest** recording each vendored library and its exact version, in one file
- a documented refresh procedure
- the manifest is what a security advisory is checked against — without it, "which Tabulator are we on?" has no answer

### 17.6 What does not change

`django-ckeditor-5` already ships its own static files through its Python package, which is exactly this pattern arriving from a dependency rather than from us. It needs nothing.

## 18. Extension points

Fourteen extension points, ordered by the layer that provides each. Together they are plinta's public API — the surface that may not break without a deprecation cycle. Each has a skill (§25).

Ten are `register_*` functions; the rest are a signal receiver, a `Rule` subclass, a contrib package, and a consumer application.

Every bundled package uses these and only these. A private path for bundled code would make the contract fiction, so there isn't one.

### 18.1 Add a placeholder — `utils` (§3.6)

```python
@register_placeholder('current_quarter')
def current_quarter(ctx):
    return quarter_of(date.today())
```

Resolves a token inside filter-style values. Returns a **value**, never a field path or an operator, and the returned type must match the declared lookup.

### 18.2 Add a date range — `dates` (§3.2)

```python
@register_range('current_fiscal_year', 'Current Fiscal Year')
def current_fiscal_year(field, today):
    return Q(**{f'{field}__gte': fy_start(today), f'{field}__lte': fy_end(today)})
```

Returns a `Q` over the **field it is given**, so one range serves every date column. The label is what a filter bar offers. Distinct from a placeholder, which returns a value rather than a query.

### 18.3 Register a widget override — `forms` (§12.3)

```python
register_widget(ChartConfig, 'series', 'chart/series_editor.html')
```

Replaces the derived widget for one field of one config schema, where the annotation carries no shape — `list[dict[str, Any]]` and its kind. Keyed by the schema **class**, so a misspelled field raises at import instead of registering an override that never fires.

### 18.4 Listen to an event — `events` (§4)

```python
@receiver(object_written)
def on_write(sender, obj, mode, changes, actor, source, **kw):
    ...
```

Never import the emitter. Handlers must be fast and must not raise — a raising handler is logged and swallowed, and must never fail a user's save. Anything slow belongs in a queue you own.

Available: `object_writing`, `object_written`, `object_deleted`, `state_changed`, `comment_posted`. Every one carries the same envelope — `obj`, `actor`, `source` — so a handler subscribing to several reads one shape (§4.1).

**To emit rather than listen**, call the matching `emit_*` function; a consumer needing an event plinta does not have declares a plain `django.dispatch.Signal` in their own app (§4.5).

### 18.5 Add a policy — `permissions` (§5.3)

```python
# consumer's policies.py — autodiscovered
register_policy(Instrument, InstrumentPolicy)
```

A **scope provider is a policy**, not a separate mechanism — bind `FieldInUserSet` to your own tenancy and register it:

```python
class DeskScopedPolicy(PermissionPolicy):
    view = FieldInUserSet(field='desk', user_set=lambda u: u.desks.all())
```

Core's engine never imports a provider. `contrib.organization` is one provider, not the provider.

### 18.6 Add a rule — `permissions` (§5.4)

Subclass `Rule` and supply both halves from one declaration:

```python
class Owner(Rule):
    def to_q(self, user):        return Q(owner=user)
    def evaluate(self, user, i): return i.owner_id == user.pk
```

**The two must never disagree** — a row surviving `to_q` must pass `evaluate`. That invariant is the reason the pairing exists.

### 18.7 Add a queryset modifier — `datasources` (§6.4)

```python
@register_queryset_modifier('overdue_only')
def overdue_only(qs, request, **kw):
    return qs.filter(due_date__lt=today())
```

Registration is mandatory: configuration names a registered key, never a dotted import path, so a saved config cannot cause arbitrary code to be imported. May narrow; must not widen.

### 18.8 Add a computed column — `datasources` (§6.10)

```python
@register_annotation('order_total', output_field=DecimalField())
def order_total():
    return F('qty') * F('price')
```

Argument-free by design. A `DataSourceField` naming it gets a column that **sorts and filters in the database**, which a `@property` cannot. Read-only, and it gets its own field permission.

### 18.9 Add a renderer — `renderers` (§7.1)

```python
@register_renderer('csv')
class CsvRenderer(Renderer):
    def render(self, rows, fields, config, user): ...
```

Rows and fields arrive already filtered by row policy and field permission. **A renderer must never query** — that is what makes it structurally incapable of widening access.

### 18.10 Add a field renderer — `renderers` (§7.8)

Declares how one value renders **and what it needs joined**, which is what lets prefetch derivation (§6.5) see relations no column names. Replaces the `serialize_for_table` / `table_select_related` duck-typing.

### 18.11 Add a component — `components` (§7.2)

```python
@register_component('heatmap', label='Heat map')
class HeatmapComponent(Component):
    config_schema = HeatmapConfig      # pydantic, extra='forbid'

    def render(self, config, user, **ctx) -> str: ...
```

Register from your own `AppConfig.ready()`; ship the template, assets, adapter and vendor with the package. The config arriving is **already resolved** — never merge a saved-view delta.

A Block referencing an unregistered type renders an empty slot, so removing your package degrades pages rather than breaking them.

### 18.12 Add a capability — `blocks` (§8.5)

Attaches a section to a model's detail page and a row to the capability matrix. A capability declares a probe and a template; the probe decides whether a model opts in, conventionally by checking for a generic relation.

**Register both aspects from your own app.** Core does not enumerate them — that it currently does for seven packages is the defect §8.5 removes.

### 18.12a Add a shell link — `shell` (§10.2)

Puts a screen in the sidebar that is not a `Page`. Registered from the owning app with a label, a URL name and the permission it needs, so the shell names no package it does not own and a link cannot outlive the app behind it.

**Prefer a `Page`.** A composition seeds one and appears in the menu already permission-filtered, shareable per row, and rearrangeable in the browser. A link is for a screen with no composition to record — a wizard, a console, a builder.

### 18.13 Ship a contrib package — (§14.0)

Register from `AppConfig.ready()`, declare `requires` / `enhances` / `composes`, ship your own models, migrations, templates, assets, adapter and **skills**, and pass the import-boundary test.

### 18.14 Build a consumer application — (§1.4)

The widest door, and the one most people use. A consumer is an ordinary Django project that installs plinta:

- **Models stay plain Django.** No base class is required by anything plinta ships, including `contrib.workflow`: a model in a workflow declares its own state column and is registered, the same way a policy is.
- **Register what should be visible** as DataSources, in a data migration or a seeder.
- **Declare policies** for row and field access; core's rule vocabulary composes them (§5.4).
- **Compose screens in the browser**, or seed Pages and Blocks so a fresh install arrives usable.
- **Create the groups and grant the permissions.** Core mints; it never grants (§18.14a).
- **Depend on anything.** Core, contrib, several packages at once — the sideways rule (§2.5) governs what plinta ships, not what is built on it.

#### 18.14a Core mints permissions; it never grants them

Three things mint, and all of them happen without being asked:

| What | Minted by | When |
|---|---|---|
| `view_page`, `change_block` and the rest of plinta's own | Django | `migrate` |
| `view_book_title` and the other column permissions | the `DataSourceField` signals (§6.9) | a column is configured |
| `export_book` and other registered actions | `mint_for` (§5.5) | a DataSource is registered |

**Nothing is assigned.** Plinta ships no groups, and a new user's menu is empty until someone grants. That is deliberate: which roles an organisation has is a policy, not a mechanism, and a `Plinta Viewer` group in core would be core deciding an organisation's shape — the same reason there is no currency symbol setting (§6.8) and no CSS framework (§10.8). A superuser bypasses both tiers (§5.9), so a fresh install is administrable from the first login.

**A consumer creates the groups.** `example/catalog` ships a command that does, and is the worked example.

**Grant after configuring, not before.** Column permissions are minted when a `DataSourceField` is saved, so a role built before the screens exist grants `view_sale` and none of its columns — and every table renders with no columns at all, silently. The order is `migrate` → configure the DataSources → create the groups; `example/catalog`'s seeder calls its own `setup_groups` last for exactly this reason.

**So a role should derive its column permissions rather than list them.** Thirty codenames written out by hand go stale the first time a screen changes:

```python
# every view_<model>_<column> minted for a model the role may view
Permission.objects.filter(
    content_type__app_label=app_label,
    codename__startswith=f"view_{model}_",
).exclude(codename__contains="_instance_")
```

The `_instance_` exclusion matters: a per-row grant (§5.10) shares the prefix, and sweeping one into a group would hand every member somebody's individual share.

**Five permissions gate a dashboard before any of the consumer's own matter:**

```
view_page  view_block  view_savedview  view_filterset  view_datasource
```

**Two of them fail silently.** Without `view_savedview` personalisation stops working with no error anywhere; without `view_filterset` saved filter sets vanish from the picker. A viewer granted only the obvious two gets a dashboard that mostly works with two features quietly dead. There is no boot check for this — a grant is a deployment decision, and a check that scolded an administrator for a role they meant to create would be noise — so it is written here instead.

Nothing here is privileged. `example/catalog` is written against exactly this list, and a consumer that needs something not on it has found a gap in the public API, not a reason for a private path.

### 18.15 Declaring relationships

```python
class MyAppConfig(AppConfig):
    requires = ['plinta.datasources', 'plinta.blocks']   # core — error if missing
    enhances = ['plinta.contrib.labels']                 # optional — info only
```

`composes` exists for a **structural** dependency — a base class, a `ForeignKey`, a migration `dependencies` entry, the `flatpages` → `sites` shape. It is checked as a boot error because it cannot degrade. `enhances` covers everything else and must name a substitute with the same interface, never a guard that hides a feature. See §2.5.

The register of declared relationships is §2.5, and it is the only place they are listed.

### 18.16 Stability

These six points, the six event signatures, and the `render` contracts are the public API — and so is the **front end a consumer overrides** (§10.8): the class names core emits, the context each template receives, and its block names. Overriding a template is a supported extension point, so those three carry the same obligation as the Python; without that, the promise is broken every release.

Everything else — module layout, internal helpers, which regions a template is split into — may change without notice.

---

## 19. Settings

Every setting plinta reads. A consuming project sets none of them to get a working install; each has a default.

### 19.1 Core

| Setting | Default | Effect |
|---|---|---|
| `PLINTA_SITE_NAME` | `"plinta"` | the name in the topbar, titles and notification emails |
| `PLINTA_PROJECT_LABEL` | `"Project"` | how the permission console groups a consumer's own models |
| `PLINTA_LOGIN_EXEMPT_PREFIXES` | the auth paths | which URLs `LoginRequiredMiddleware` lets through (§10) |
| `PLINTA_API_PREFIX` | `"/api/v1/"` | where the public API mounts (§15) — leading and trailing slash, because it is prefix-matched |
| `TOPBAR_COLOR` | unset | pins the topbar colour in light mode, so staging does not look like production |

`AUTH_USER_MODEL`, `LOGIN_URL`, `DEFAULT_FROM_EMAIL`, `MEDIA_ROOT`, `MEDIA_URL` and `STATIC_URL` are Django's; plinta reads but never requires them. `LOGIN_URL`, `STATIC_URL` and `MEDIA_URL` are read by `LoginRequiredMiddleware` alone, to build its exempt list.

**Media is not a permission boundary.** Exempting `MEDIA_URL` from the login gate is correct — in production the web server serves that path and Django never sees the request. It means attachment files must not be reachable by guessing a URL: `attachment_download` streams them through a permission check, and `storage.url()` is never rendered into a template. A consumer pointing `MEDIA_ROOT` at a publicly served directory defeats that, and no setting can stop them.

### 19.2 Contrib

| Setting | Owned by | Effect |
|---|---|---|
| `ATTACHMENT_BUCKETS` | `attachments` | model → storage backend routing |
| `ATTACHMENT_MAX_SIZE_MB` | `attachments` | per-file limit |
| `ATTACHMENT_ALLOWED_EXTENSIONS` | `attachments` | allow-list; empty means all |
| `ATTACHMENT_MAX_PER_INSTANCE` | `attachments` | default 50 |
| `PLINTA_AUDIT_EXCLUDE_APPS` | `audit` | app labels not recorded; defaults to plinta's own configuration |
| `EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL` | `notifications` | Django's own, used by `send_queued_email` |
| `FLEXMONSTER_LICENSE_KEY` | `components.pivot_flexmonster` | required by that package, which is not installed unless you want it |

**A contrib setting is read only by its own package.** Core never reads `ATTACHMENT_MAX_SIZE_MB`, and the shell never reads a pivot vendor's — which is why that context processor moves (§10).

**`PLINTA_PIVOT_PROVIDER` is deleted rather than moved.** It chose between two vendors inside one package; with a package per vendor (§11) the choice is which one is in `INSTALLED_APPS`, and a setting that duplicates that can only disagree with it.

### 19.3 `PLINTA_API_PREFIX` does not mount anything

Today the setting only *describes* a path. The consuming project mounts the API itself — `path("api/v1/", plinta_api.urls)` — and `LoginRequiredMiddleware` separately reads `PLINTA_API_PREFIX`, defaulting to `"/api/"`, to decide what to exempt from the login redirect. Two places must agree and nothing checks. It works out of the box only because `/api/` is a prefix of `/api/v1/`; mount at `/rest/` without updating the setting and every XHR caller gets an HTML redirect instead of ninja's JSON 401.

**The setting becomes authoritative — plinta mounts its own API.**

```python
# plinta/urls.py
urlpatterns = [path(settings.PLINTA_API_PREFIX.lstrip("/"), api.urls), ...]

# the consuming project's urls.py
path("", include("plinta.urls")),        # not path("api/v1/", plinta_api.urls)
```

`LoginRequiredMiddleware` reads the same value for its exempt list, so the mount and the exemption cannot drift. A system check validates the leading and trailing slash, since it is prefix-matched against `request.path`.

### 19.4 Two to remove

**`STATUS`** — one name, three reads, two unrelated meanings.

| Read | Source | Means |
|---|---|---|
| `deployment_env` | `settings.STATUS`, default `"DEV"` | the topbar environment badge |
| `auth_urls.py` | `os.environ["STATUS"]`, default `"DEV"` | the same badge, on the home page |
| `project_group_label()` | `settings.STATUS`, under `PLINTA_PROJECT_LABEL` | the consuming project's display name |

Two live defects follow. The home page reads the **environment variable** while every other page reads the **setting**, so setting one and not the other makes them disagree — and because it sits in a URLconf `extra_context` dict, `os.environ` is read once at import and never again. Separately, a consumer who sets `STATUS = 'PROD'` for the badge and has never heard of `PLINTA_PROJECT_LABEL` finds their model group in the permission console labelled **"PROD"**.

**It is deleted, not renamed.** The badge itself goes with it: `TOPBAR_COLOR` already distinguishes environments in the same topbar, and a colour does it at a glance without consuming horizontal space. Two mechanisms for "staging must not look like production" is one too many, and the one that survives is the one that cannot disagree with itself.

`PLINTA_PROJECT_LABEL` loses the fallback and defaults to `"Project"`. It is a heading in the permission console — the consumer's own models group under it, plinta's and Django's group under "Plinta" — so it names a project, never an environment.

**`MIGRATION_MODULES`** appears in plinta's own test settings as a stub for the legacy `runtests` command, which is deleted (§22). No consuming project should ever set it for plinta.

### 19.5 Rule

A new setting needs a default that works, an owner (core or a named contrib package), and an entry here. A setting read in two places with two meanings is the defect `STATUS` demonstrates.

---

# Part V — Reference

## 20. Conventions



### 20.1 Package layout

```
plinta/<layer>/            core
plinta/contrib/<app>/      contrib
```

Every app: `apps.py` (declaring `requires` / `enhances` / `composes`), `models.py`, `api.py` (its router), `policies.py` (its permission policies), `migrations/`, and its own templates and static under a namespaced directory.

**An app package's `__init__.py` re-exports nothing.** Django imports the package before its models are loadable, so an `__init__` reaching them — directly, or through any module that imports them — raises `AppRegistryNotReady` and the app cannot be installed at all. Callers import from the module. Packages with no models re-export freely; the rule follows the models, not the layer.

A component ships with whatever owns it. Core never lists optional components.

### 20.2 `app_label` is pinned and permanent

Every `AppConfig` sets an explicit `label`. Moving a package must not change it.

Content types, generic relations and permission codenames are all keyed on `app_label`. A consumer writes `GenericRelation("labels.LabeledItem")` in their own models and migrations; changing the label breaks their code and orphans their rows.

Pinning is what lets `plinta.labels` become `plinta.contrib.labels` as a pure import-path change, with no data migration.

### 20.3 A check belongs to the layer that can see what it validates

`django.core.checks` functions are registered per app, and every layer
registers its own. A layer cannot check what it cannot import, so a check is
owed by whoever holds the configuration it reads — not by whoever noticed it
was needed.

| Check | Reads | Owed by |
|---|---|---|
| a `HasPerm` naming an unminted codename | the policy registry | `permissions` (§5.13) |
| a DataSource-backed model with no policy | DataSources | `datasources` (§6.9) |
| a `DataSourceField` naming an unregistered annotation | DataSourceFields | `datasources` (§6.9) |
| unresolved placeholder tokens | stored filter dicts | `blocks`, `pages`, `contrib.reports` (§3.6) |
| `LoginRequiredMiddleware` absent | `settings.MIDDLEWARE` | `shell` (§10.4) |

**A check that reads rows must survive an unmigrated database.** Checks run
during `migrate`, so one that queries returns nothing on a `DatabaseError`
rather than raising — failing there blocks the migration that would fix it. A
check reading only settings or a registry has no such problem and should raise
normally.

### 20.4 The import boundary is a test

`tests/test_import_boundary.py` walks the AST of every core module and fails if one imports `plinta.contrib`. It also fails when a contrib package imports another without a declared `enhances` or `composes`.

The rule is enforced mechanically because a rule enforced by discipline is a rule that lasts until the first deadline. Every coupling in the previous design was added by someone who knew better and was in a hurry.

### 20.5 Before adding a registry

The design carries registries for annotations, queryset modifiers, placeholders and date ranges. Before a fifth: **if a proposed registry shares an input shape and an output shape with an existing one, it is the same registry under another name.**

Passing that test is necessary, not sufficient. A mechanism must also be worth its weight — a query-parameter registry for resolving saved filters by id was genuinely distinct and still rejected, because one boolean on one model achieved the same thing.

### 20.6 The JS mirrors the package layout

A component's adapter ships with its component; a contrib app's front-end code ships with that app; core carries the client and the chrome, and nothing else. Same layering as the Python, same one-way rule.

The import-boundary test covers JS as well. A regex over import paths is cruder than the AST walk, but it catches what matters — and without it the front end drifts while the back end is policed, which is how `contrib.notifications` code ended up inside core's `core.js`.

### 20.7 Optionality is a CI job, not a claim

Two installs are supported and both are exercised:

- **minimal** — core only, eleven packages
- **full** — core plus every contrib package

CI boots both, runs the suite against both, and renders a page under each. Optionality that is not tested is optionality that has already broken.

### 20.8 Migrations

- One `0001_initial` per app until there is a reason otherwise.
- No migration in core may depend on a contrib app. This is checkable and is checked.
- Data migrations that fix up a one-time upgrade are deleted once every deployment has passed them; they are not carried forever.

### 20.9 Permissions

**Every function that reads data takes a user, and it is required.** There is no unfiltered path and no system user (§6.3). A parameter typed `user=None` is a security defect waiting for a caller: the caller that forgets it gets every row instead of an error.

Omitting it must raise `TypeError` at the call site. A management command that legitimately acts for no one passes an explicit sentinel and is read as unusual, rather than looking like an ordinary call with an argument missing.

### 20.10 Testing

- Tests live beside the code they test: `x.py` is tested by `test_x.py` in the same package. A module with no matching file is a module nobody checked, and the pairing makes that visible without a coverage tool.
- A contrib package's tests must pass with only core and that package installed.
- The integration suite — booting a real consuming project, seeding it, rendering through the test client — runs in CI. It covers the `reverse()` and template surface a package-only suite cannot reach.

### 20.11 Naming

Component types are lowercase and hyphenated: `details-card`, `comments-section`.
Event signals are past tense: `object_written`, `state_changed`.
Capability names are singular nouns: `comments`, `labels`, `audit_history`.

### 20.12 Documentation

State the decision. Where a decision has a non-obvious consequence, state the consequence. Do not record the debate.

A docstring or reference page describing a config key must name the code path that reads it, and must be checked against that path when the key changes. Four documented behaviours in the previous design were never implemented (§21); prose that nobody verifies is worse than no prose, because it is ported.

A decision that changes the architecture gets an ADR in `design/adr/`; a decision that only affects one layer belongs on that layer's page.

**Code cites an ADR, never a section of this document.** `ADR 0006` is stable by convention and immutable by design. `§5.4` is a pointer into a numbering that moves — the same name-as-reference defect §8.1 removes from `SavedView.block_name` and §8.9 from block URLs. A docstring naming a section is a broken link waiting for the next reorganisation.

### 20.13 What survives the build

This document is mostly a **plan**, and a plan that outlives its execution becomes a second source of truth for facts the code already states. That is how four of v1's documented behaviours came to describe something the code never did (§21.11).

So when the last layer lands, it splits.

| Part | Fate |
|---|---|
| §24 — the eight decision records | **Kept**, one file each under `design/adr/` |
| §1–§2 — purpose, layers, the membership tests, the dependency rules and their register | **Kept** as `design/architecture.md` |
| §3–§19 — the layer specifications | **Retired.** The code answers *what*; a consumer's questions are answered by user documentation |
| §21, §22 — the ledgers | **Retired.** They record what became of v1's features, which stops mattering once nothing is left of it |
| §23, §25 — build order, the skills plan | **Retired.** They expire on completion by definition |

**Retired means tagged, not deleted** — `v2-spec`: recoverable, and nobody has to keep it true. Recoverable, and nobody has to keep it true.

What survives is the part that cannot drift: an ADR records a decision at a moment and never claims to describe current behaviour, and `architecture.md` states rules the import-boundary test enforces mechanically.

---

## 21. Feature decisions



A feature survives a rebuild by default — whoever ports the table ports everything in it, because it is there, not because anyone chose it. This ledger makes the choice explicit.

**A layer is not done until every ledger row for it is resolved.** That is part of the definition of done in §23.

### 21.1 Evidence basis

Usage counts come from a live consuming project: **44 DataSources, 279 DataSourceFields, 54 Blocks, 36 Pages**. "0 uses" is evidence, not proof — a feature may have been used by a consumer that has since been separated. Where that is known, it is stated.

Decisions: **keep** · **keep + fix** · **drop**. There is no *open* state — a row without a decision is a row that will be ported by default, which is what this ledger exists to prevent.

---

### 21.2 `datasources` — DataSourceField options

**The decisions live in §6.2**, with the layer that owns them. They are not repeated here: this table existed in two places and the copies disagreed on four rows — `editor_widget`, `edit_modal_block`, `editor_queryset_filter` and the two additions — which is the drift a single document is supposed to make impossible.

What follows is the reasoning behind three of those rows, which §6.2's table has no room for.

#### `is_fiscal_year` / `is_month` — drop

Adds "Current / Prior Fiscal Year" and "Current Month" placeholders to a filter dropdown, for fields storing fiscal year or month **as integers**. Fields are auto-detected by name suffix (`*_fiscal_year`, `*_month`); these flags are the manual override for non-conforming names.

A denormalised ERP schema convention, driving behaviour from a column-naming pattern in core. Replaced by the design already recorded: calendar ranges in core `dates`, fiscal ranges registered by `contrib.organization` into the same resolver (ADR 0006 (§24)). Core need never know a column holds a fiscal year.

#### `recompute_siblings` — drop the flag, invert the default

After an inline edit, re-fetches the row through the component and returns it as `updated_row`, so server-derived sibling columns refresh in place. The ERP case is editing a quantity and watching a total update.

Zero uses — but note the consequence: **without the flag, an inline edit returns no updated row at all.** So do not delete the capability; invert the default. Always return the updated row after a write: one refetch, no config, better behaviour, one option fewer.

---

### 21.3 `components.table`

| Feature | Used | Decision | Notes |
|---|---|---|---|
| `page_size` | 46 | keep | |
| `title` | 37 | keep | |
| `enable_export` | 34 | keep | moves with `contrib.export` |
| `sort` | 32 | keep | |
| `edit_form_template` | 18 | keep | |
| `enable_create` | 2 | keep | |
| `create_defaults` | 2 | keep + fix | one magic string, resolved in two places — below |
| `row_formats` | 1 | keep + fix | below |
| `row_link_field` | 1 | keep | |
| `height` | 0 | keep | Tabulator passthrough |
| `queryset_modifier` | — | keep | lives on the Block field, not in config |
| `expand_columns` | 0 | **drop** | below |

#### `expand_columns` — drop

Fans a reverse FK into repeated columns (`Item 1`, `Item 2`, …), sized to the widest row on the page. Requires the consuming model to implement `expand_for_table()`, optionally `expand_color()`.

Zero uses here, and **its only implementation lived in the client project that has since been separated.** Orphaned rather than broken.

Removal covers `_compute_expand_metadata`, 5 context fields, 34 references in `component.py`, 13 in `api.py`, the `dynamic_columns` response key, and the column-injection path in `table.js`.

Keep the sibling feature — a reverse relation rendered as **one stacked cell** — which is live (`labeled_items` on 8 DataSources).

#### `create_defaults` — keep, fix

Pre-fills fields when a user clicks "+ New": `{"owner": "__CURRENT_USER__"}` sets the new record's owner to whoever clicked. Both uses in the surveyed install came from `seed_actions_page.py`, which leaves with `actions` — so the placeholder ships with no shipped consumer and is kept on the strength of the mechanism, not its usage count.

Conventional and worth keeping — every CRUD tool pre-fills "assigned to me". Two defects:

**Resolution is duplicated.** `blocks/api.py:464` pre-fills the create *form*; `write_pipeline.py:493` applies defaults on *save*. Same loop, same placeholder check, written twice — so they can drift, and the form would then show a value the pipeline does not save. One resolver, called from both.

**The placeholder is a magic string, not a mechanism.** Exactly one exists (`__CURRENT_USER__`). Replace it with a small registry of named placeholders — `current_user`, `today`, `now` — matching the extension-point pattern used elsewhere, so a consumer can register their own without touching core. Keep the set closed: named placeholders, never expressions.

!!! warning "The docstring describes a feature that does not exist"
    `components/tables/component.py:77` claims values *"may be literals or template strings (`{{user}}`, `{{today}}`), resolved via `apply_field_value` in `blocks/views.py`."* All three claims are false: the syntax is `__CURRENT_USER__`, `apply_field_value` is a type-coercion helper that resolves nothing, and `plinta/blocks/views.py` does not exist. There is no `{{today}}` equivalent at all.

    This is one of four such findings, tabulated in §21.12. **Treat docstrings and reference docs as unverified during the rebuild.** Behaviour is read from code and confirmed against usage, never ported from prose.

#### `row_formats` — keep, fix as encountered

Conditional row styling: `{field__op: value}`, eight operators, a magic `"today"`, implicit AND. Conventional for a table widget, and declarative, so styling stays editable in the browser rather than becoming developer-only.

One known defect: comparisons are string-based, so `lt` / `gt` on a numeric column are lexicographic (`"9" > "10"`). Correct for ISO dates, which is the shipped use. Fix by typing the comparison from the `DataSourceField`. Freeze the operator set — when `OR` or arithmetic is wanted, the answer is a component or a queryset modifier, not a bigger language.

---

### 21.4 Model protocols

Plinta silently requires methods on a consumer's model. §1 promises it requires nothing of them, so these are the same imposition under another name.

| Protocol | Implemented by | Decision |
|---|---|---|
| `expand_for_table()` | left with the client project | **drop** |
| `expand_color()` | left with the client project | **drop** |
| `serialize_for_table()` | `Label` | keep, **redesign** |
| `table_select_related()` | `Label` | keep, **redesign** |
| `get_notification_recipients()` | `Action`, which leaves plinta (ADR 0008 (§24)) | keep as an extension point, **redesigned** — an explicit subscription, with no shipped implementer |
| `duplicate(user)` | `Action` | the model leaves plinta; the hook stays, with `Block` and `SavedView` as its reference implementations (§8.10) |

**Redesign** means replacing `hasattr` duck-typing with a declared, registered extension point: the table cases become one **field renderer** registration, the notification case an explicit subscription.

**`status_changed_at` / `status_changed_by` are not a model protocol and were listed here in error.** Core never reads or writes them.

**And with no base class to declare them, they do not survive as fields at all.** Who moved a row and when is what `state_changed` carries and what the audit trail records, so a second copy on the consumer's model could only disagree with it. A consumer wanting the columns anyway declares them and stamps them in an `object_written` subscriber, like any other derived value.

---

### 21.5 `accounts`

| Feature | Decision | Notes |
|---|---|---|
| `CustomUser` | **drop** | ADR 0002 (§24) — the consumer owns the user model |
| `duplicate_user` admin action | **drop** | below |
| `UserCompanyAccess` / `UserBusinessUnitAccess` | move | → `contrib.organization` |
| permission console | move | → core |

#### `duplicate_user` — drop, and record the defect

Clones a user with groups, permissions and org accesses as `<username>_copy`.

It sets `user.pk = None` and saves, so **the password hash is copied and never reset**, and `is_active` carries over. The clone is immediately loginable with the source user's password.

It disappears with the user admin under ADR 0002 (§24). Recorded so the behaviour is not reproduced: any future "copy this user's access" feature copies grants only, never credentials.

---

### 21.6 `datasources` — other

| Feature | Decision | Notes |
|---|---|---|
| FK object search: `hasattr(model, 'site')` | **drop** | appends `" (site)"` to the label of any model with a `site` field, and adds `select_related('site')`. Hardcoded org knowledge in a core endpoint. |

---

### 21.7 `pages` — swept

**The decisions live in §9.1 and §9.8**, with the layer that owns them, and are not repeated. The census behind them: 36 pages, of which `page_type` is set on all 36 (dashboard 27, custom-template 7, detail 2), `template_name` on 7, `context_param` on 2, `tabs` on 1, and `config`, `is_system`, `external_url` and `PageFilterMapping` on none.

Two of those zeroes resolve differently, which is the whole reason the count is evidence rather than proof: `is_system` and `external_url` are dropped because each is a mechanism the design replaces, while `PageFilterMapping` is deferred because it is `pages/0003` — newer than the install that shows no rows.

### 21.8 `contrib` — swept

**The decisions live in §14**, per package, and are not repeated. What the sweep established:

- every contrib package has a usage census and a decision for each of its features
- one app carries zero rows in the surveyed install — `notifications` — and is kept, because it supplies a shipped screen and absence of use in one install is not absence of purpose
- one app is not shipped at all: `actions` (ADR 0008 (§24))
- workflow's transition flags — `requires_confirmation`, `requires_comment`, `permission_codename`, presentation — are all in use and all kept

### 21.9 `audit` — create rows carry no field data

`record_changes(mode='create')` writes a single row with `field_name=''`, `old_value=None`, `new_value=None`. The trail says "Created" and nothing more, so the initial state of a record is not recoverable from the log.

That makes the log only conditionally replayable: current state can be wound backwards through the changes, but only if no unaudited write ever happened — and §4.4 makes that likely, since plinta only emits for writes it mediates.

**Decision: keep one row, put the initial values in `metadata`.** `AuditLog` already has that JSON column, so it costs nothing structurally, and the timeline still reads as one "Created" entry rather than twenty. One row per field on create would drown the timeline for no gain, since a create has no per-field *before* to compare against.

### 21.10 `audit` — `record_restore` is unreachable

Called by nobody. Its docstring describes it as *"the symmetric companion to `record_delete` for consuming projects"*, so it was written as an offering rather than for a plinta code path — and no plinta code path restores anything.

**Dropped with the `object_restored` signal (§8.10).** A consumer with soft delete flips a flag, which is an update: `object_written` carrying `changes={'is_deleted': (True, False)}` names the field and both values, which is more than a bare restore row ever could.

### 21.11 Cross-cutting sweep: documentation drift

**Four** documented behaviours in the previous design do not exist in its code.

| Where | Says | Actually |
|---|---|---|
| `create_defaults` docs | a `{{user}}` / `{{today}}` template language | never implemented; the docs name a resolver and a file that do not exist |
| `expand_columns` docs | several config keys | its own docs note that earlier drafts described keys that "are not read" |
| `Block.queryset_modifier` help text | *"Dotted path to a function that modifies the queryset"* | the field stores a **registered key**; an unregistered name hard-fails at save |
| `gantt.critical_path` | a config option, in the schema and a docstring | accepted, validated, and ignored — it appears nowhere else |

Every one would have misled someone porting the feature from its description, which is exactly how a rebuild reintroduces a feature that was never there.

Two consequences. A sweep comparing every documented config key against the code path that reads it is its own task. And until it is done, **behaviour is established from code and usage, never from prose** — the same rule §25.3 applies to the v1 skills.
### 21.12 Sweep complete

Every layer and every contrib package has a usage census and decisions. Two items are recorded as **deferred with a use case** rather than dropped — `PageFilterMapping` (§9.4) and the general `visibility` field the sharing spine does not yet need (§5.10) — and one as an accepted trade: publishing means giving up ownership.

The sharing **UI** is the only surface not separately swept; it is generated from the spine (§5.10) rather than hand-built per model, so it has no independent feature set.


---

## 22. Deferred and deleted

Everything decided as "not in v2", in one place, each with the use case that would bring it back. Nothing here is hedged elsewhere in the document — a layer section states what is built, and this section states what is not.

### 22.1 Deferred features

| Feature | Why not now | What brings it back |
|---|---|---|
| **`PageFilterMapping`** — one filter across several DataSources | New (`pages/0003`), never exercised. A page whose blocks share a DataSource needs nothing, and a mixed page can declare a filter per source. | A dashboard that genuinely needs one control mapping to `sector`, `instrument__sector` and `instrument__sector__code` across three blocks. |
| **A general `visibility` field** on shareables | The single-axis model — public means owner-less — is accepted, and publishing means giving up ownership (§14.1). | A second shareable needing *owned and public*. Reports needed it and was normalised instead; a second case means the spine is wrong, not the app. |
| **A query-parameter registry** for the public API | The caller expands a saved filter in two calls, and the design already carries four registries — a fifth must earn its weight (§20.4). | `?filterset=` being asked for repeatedly, by someone real. |
| **Bulk write endpoints** in core | The write pipeline is single-row by design; its per-row authorise, validate and emit are what make it the only mutation path. | A contrib importer, which loops the pipeline inside `events.batch()` rather than bypassing it. |
| **A bundler and TypeScript** | Vendored assets solve the CDN problem without importing npm's maintenance surface (§17). | The JS settling into one client and N adapters, at which point what would be compiled is clear. |
| **Custom elements** for adapter mounting | ES modules with an import map do the job. | HTMX swaps making manual mount-scanning painful enough to notice. |

### 22.2 Deferred, with the shape already settled

**Derive field defaults from the Django model.** Registration stays manual for now. When revisited, the shape is:

- Store `NULL` = **inherit**, derive at read; do not snapshot into the row. Same principle as ADR 0004 (§24) — a `SavedView` stores a delta so a change to the block reaches it. Snapshotting field config forks silently: change `verbose_name` or `decimal_places` later and 279 rows keep the old value with nothing marking them stale.
- The UI shows the derived value greyed as a placeholder; typing over it stores an override, clearing it returns to inherit.
- Derivable: `label` ← `verbose_name`, `sorter` ← field type, `header_filter` ← field type, `format` ← field type, `decimals` ← `DecimalField.decimal_places`, tooltip ← `help_text`.
- **Bulk import at registration** is the larger win — offer every concrete field on the model and let the user prune, rather than creating rows one at a time.
- Wrinkle: `field_name` may traverse (`company__code`), name a reverse accessor, or be a `@property`. Derivation walks the path where it can; where it cannot, it falls back to string, no format, read-only.

*(Query hints as a config option were considered and rejected — derivation already computes them. See §6.5.)*

**`searchable` per field.** The explicit override once the defaults in §6.6 are right: makes a hidden identifier searchable (an ISIN that is not displayed but is typed), or excludes a visible long-text column that is useless to match on. Follows the defaults rather than replacing them — the corrected defaults improve all 273 fields that configure nothing, the flag serves the minority.

### 22.3 Deleted, and not coming back

Each was removed for a reason that does not expire.

| Feature | Reason |
|---|---|
| `expand_columns` — reverse FK fanned into repeated columns | Orphaned; its implementation left with the client project |
| `expand_for_table()`, `expand_color()` model protocols | Ditto |
| `is_fiscal_year`, `is_month` | Behaviour driven by a column-naming convention |
| `recompute_siblings` flag | The behaviour becomes unconditional, so the flag has nothing to gate |
| `edit_modal_block` | A block edits its own DataSource's records, never another's |
| `editor_queryset_filter` | An arbitrary ORM filter in configuration, unenforced on write |
| `StaffOnly` rule, and `is_staff` as a grant | A Django flag acting as a permission |
| `DenyAll` rule | Unused; the deny path is a constant |
| `object_restored` signal, `record_restore` | A restore is an update, and it names the field and both values |
| `Page.is_system` | A flag acting as a permission |
| `Page.external_url` | A second routing mode inside a model that also has a grid |
| `admin_only` on menu sections and groups | Menu visibility already follows the pages inside |
| `FilterSet.is_active` | A personal preset is deleted, not disabled |
| `ScheduledReport.report_code_name` and the code registry | A second mechanism for one concept |
| `ReportDefinition.is_public` | Normalised onto the shareable model |
| `SavedView.view_type` | Derivable from `block.component_type` |
| `gantt.critical_path` | Declared, validated, and never implemented |
| `kpi.decimal_places` | `DataSourceField.decimals` is honoured by every renderer |
| `HTML_KWARGS` | Fragments leave the OpenAPI framework entirely |
| `runtests` management command | Superseded by the pytest harness |
| `duplicate_user` admin action | Copied the password hash without resetting it; dies with the user model |
| `duplicate_page` service | `copy_to` walks a model's declared children instead (§8.10) |
| `STATUS` and the topbar environment badge | One name, three reads, two meanings; `TOPBAR_COLOR` distinguishes environments and cannot disagree with itself (§19.4) |
| `contrib.actions` and `Urgency` | Plinta ships facilities, not domains; a task tracker with `responsible`, `urgency` and `blocked_by` is one application's domain. Rebuilt as a consumer app if wanted (ADR 0008 (§24)) |
| Global slug uniqueness for pages | Five hundred people cannot negotiate over `my-dashboard` |
| Expressions in configuration | Strictly less capable than registered annotations, and a parser is a security surface |
| Deny rules that override allow | Order-dependent decisions, and `explain()` becomes an argument |

## 23. Build order



The rebuild proceeds bottom-up, one layer at a time. A layer is done when it imports only layers below it and its tests pass with nothing above it installed.

Nothing here is scheduled. The order is a dependency order, not a plan.

### 23.1 Sequence

Layer 1 is §3, layer 2 is §4, and so on — §1 is scope and architecture.

| # | Layer | Done when |
|---|---|---|
| 1 | `utils`, `dates`, `forms` | No plinta imports at all. Fiscal helpers separated from calendar helpers. The form engine renders and parses a pydantic schema knowing nothing of DataSource or permission. |
| 2 | `events` | Five signals defined. No emitters yet. |
| 3 | `permissions` | Imports only 1–2. `FieldInUserSet` exists; no organisation reference remains. Field-permission minting takes a model and field names, never a `DataSourceField` — the trigger arrives at layer 4. |
| 4 | `datasources` | Imports only 1–3. Every viewer-facing service takes a user. Owns the `DataSourceField` signals that drive field-permission minting, including the `pre_save` that makes a rename preserve grants. |
| 5 | `renderers` | Contract plus HTML. No Excel, PDF or email. |
| 6 | `components` | Contract, registry, `table_plinta`. No saved-view merge anywhere. |
| 7 | `blocks` | Write pipeline emits its three signals — `object_writing`, `object_written`, `object_deleted` — and computes `changes`. `SavedView` merges directly; there is no hook, which went with the optionality (ADR 0004 (§24), revised). |
| 8 | `pages` | Composition, `PageFilter`, menu. Blocks resolve by FK. Missing component and unviewable block both degrade to an empty slot. |
| 9 | `shell` | One base template and its regions. `LoginRequiredMiddleware` with its system check. Tokens generated from `tokens.json`; `lint_hex_colors` green. A logged-in user can reach a page, sort it and page it, with no vendor script loaded. |
| 10 | authoring screens (§12) | A DataSource, a Block and a Page can be created, edited and arranged entirely in the browser. |
| 11 | framework pages (§13) | `seed_platform_pages` is idempotent and yields a usable application on a fresh database. |
| 12 | contrib, in any order | Each installs and uninstalls cleanly against core alone. |

`contrib.api` is built after `blocks` and `datasources` are settled, since it is generated from them and adds no endpoints of its own.

**Contrib order is unconstrained, and that is a result rather than a rule.** It holds because no shipped package declares `composes` (§2.5) and the one `enhances` — `reports` on `export` — substitutes rather than requires. A `composes` declaration would constrain the order legitimately; if one appears, build the depended-upon package first and record the edge here.

Suggested first: `audit`. It is the strictest test of the event bus. If audit works as a pure listener, the vocabulary is right; if it needs a pipeline hook, stop and fix layer 7 before building anything else on it.

**The last step is this document.** When the final package lands, tag `v2-spec` and split it as §20.12 says: the ADRs and `architecture.md` stay, the rest retires.

### 23.2 Definition of done, per layer

1. Imports only from layers below. Verified by `tests/test_import_boundary.py`, which is written at layer 1 and runs from then on.
2. Tests pass with no higher layer and no contrib package installed.
3. Every row for that layer in §21 is resolved — no feature is ported merely because it exists.
4. Its **section in this document** matches what was built — including its `Must not know` line. Where they disagree, one of them is wrong and it is decided before moving on.
5. Its extension points have **skills** (§25), written against the layer as built.

### 23.3 The couplings this must eliminate

Every coupling found in the previous design, and where each is resolved. The rebuild is incomplete while any row is unresolved.

| Coupling | Resolution |
|---|---|
| `blocks/api.py` → `actions.models.Action` (module scope) | **deleted with `actions`** (ADR 0008 (§24)); the row-extension registry still ships, exercised by a consumer app |
| `components/kanbans/api.py:27` → `labels.models.LabeledItem` (module scope) | `labels` listens; kanban chips become a declared `enhances` (§2.5) |
| `components/kanbans/api.py:30` → `workflow.transitions.get_workflows_for_model` (module scope) | declared `enhances`, substituting field-grouped columns (§2.5) |
| `comments/api.py` → `notifications.triggers` (module scope) | emit `comment_posted` |
| `actions/apps.py` → `notifications.triggers.register` | `notifications` subscribes to core signals |
| `pages/capabilities.py` → `notifications.triggers._handlers` | capability probe stops consulting the handler registry |
| `blocks/write_pipeline.py` → `labels.models.LabeledItem` | `labels` listens to `object_written` |
| `blocks/write_pipeline.py` → `notifications.triggers.fire_notifications` | emit `object_written` |
| `blocks/write_pipeline.py` → `audit.services` (snapshot + record) | emit `object_writing` / `object_written` with `changes` |
| `workflow/mixins.py` → `notifications.triggers` | emit `state_changed` |
| `workflow/transitions.py:158` → `audit.services.record_transition` | emit `state_changed` |
| `workflow/transitions.py:205` → `audit.models.AuditLog` (reads transition history) | **not behavioural** — declared `enhances: audit`, substituting an empty history (§14.6) |
| `pages/views.py` → `attachments.storage` | capability probe; storage registered by the app |
| `blocks/api.py` → `reports.builder.ExcelReportBuilder` | `export` owns the export endpoint |
| `urls.py` → unconditional `include('reports.urls')` | contrib apps mount their own routers |
| `permissions/scoping.py` → organisation concepts by name | `FieldInUserSet` + provider |
| `pages/views.py`, `datasources/api.py`, `components/{charts,pivots}` → `organization.utils` | calendar helpers to core `dates`; fiscal registers into the resolver |
| Component registration split across `plinta/apps.py` and `components/apps.py` | each component registers from its own package |
| 46 of 81 endpoints are HTML fragments hidden from the spec | fragments move to plain Django views; ninja keeps only the public API |
| `notifications/api.py` `auth=None` — safety depends on the consumer's `LoginRequiredMiddleware` | `@login_required` on a Django view redirects natively |
| `plinta/urls.py` is a deprecation-targeted `reverse()` shim | it becomes the fragment transport and stops being deprecated |

Two template includes of the attachment section were also flagged during the audit and needed no change — both are already guarded on context variables that only populate when the app is installed.

### 23.4 v1 is another repository, not a directory

**v1 is not in this repository.** This history begins at an empty package; v1 keeps its own repository, and is read from a clone of it:

```
cd ../bmscore && git show HEAD:plinta/permissions/rules.py
```

An earlier draft kept v1 on disk, unrun, to be deleted layer by layer. That is worse for three reasons, and the third is the one that matters.

- **The tree would be half-old and half-new for the whole rebuild**, both halves called `plinta`, with `permissions` importing nine apps beside `permissions` importing three. Nobody can tell which one they are reading, and "what stays" stops being answerable by looking.
- **v1's migrations conflict with the fresh `0001_initial` §20.7 requires**, and its `app_label`s collide.
- **The import-boundary test (§20.3) would be unenforceable** until the last v1 file left. With v1 absent from the working tree it passes from commit one, which is the point of writing it at layer 1.

Reading v1 and *having* v1 are different needs. A separate repository serves the first without the second, makes an accidental import impossible rather than merely discouraged, and lets this repository be shared without sharing what preceded it.

**The tests are rewritten per layer, never ported.** A v1 test asserts v1's shape — eighteen permission functions, a fifteen-stage pipeline, `block_name` as a string — so porting one ports the design it was written against. Read the v1 test for the behaviour it captures, then write the v2 test against §N.

**One thing is ported rather than rewritten: `example/catalog`.** It is a consumer app built on the public API, and §1.4 makes it the guard that the API is real. It lands last, and anything it needs that is not in §18's twelve extension points is a gap in the API, not a reason to reach inside.

---

## 24. Decision records



### ADR 0001 — Core and contrib

**Status:** accepted, 2026-08-28

#### Context

Eighteen Django apps, ~29k LOC, all mandatory. The dependency graph had cycles: `permissions` imported nine apps and was imported by twelve; `blocks` imported thirteen; `pages` imported eleven and was imported by fourteen. There was no direction in which to read the codebase, and no way to install less than all of it.

Separately, a plugin architecture was already present and unused: capability apps registered themselves from `AppConfig.ready()`, attached by content type with zero inbound foreign keys, and had zero inbound migration dependencies. About a dozen stray imports were the only thing making them mandatory.

#### Decision

Split into **core** and **contrib**, in one repository, on one release — the `django.contrib` model.

Core ships the contract plus one reference implementation; contrib ships the rest. Membership is decided by three tests: the sentence test, the noun test (a model naming a real-world business object is contrib) and the import test (core may not import contrib).

Dependencies flow one way. Core is a closed set, enforced by an AST-walking test rather than by discipline.

#### Alternatives rejected

**Separate repositories per plugin.** Multiplies CI, versioning, releases and compatibility matrices for a project with one maintainer, and builds a plugin API for an ecosystem of one. Frappe does this successfully with a company behind it; Django, facing the same question with far more contributors, chose `contrib` and never revisited it.

**One app.** Loses the only on/off switch Django provides and gains nothing — app boundaries provide no encapsulation, since Python imports cross them freely.

**Merging the small capability apps into one.** Saves about sixty lines of scaffolding and costs table renames and content-type rewrites against live data. The ratio is indefensible.

#### Consequences

Core's dependencies become Django, django-ninja and pydantic. Its front end keeps only the chrome libraries — vendored under `static/`, never fetched from a CDN (§17), with no CSS framework (§10.8) and no grid library (§11.2) among them — so core absorbs no front-end major-version upgrade.

A minimal install is eleven packages; a full install is thirty-two. Both are supported and both are exercised in CI.

The repository may be split later — `git filter-repo` away — when a second consumer needs a different version of a package than the first. Until two consumers disagree about a version, one repository is strictly better.

### ADR 0002 — Plinta does not define the user model

**Status:** accepted, 2026-08-28

#### Context

Plinta shipped `accounts.CustomUser` and required consumers to set `AUTH_USER_MODEL = "accounts.CustomUser"`.

`AUTH_USER_MODEL` is the single most irreversible setting in a Django project. Changing it after the first migration is painful enough that projects live with the wrong choice for years. A library that dictates it is dictating the one decision a project can least afford to hand over — and plinta's user model existed mainly to carry fields that have since been deleted.

#### Decision

The consuming project owns the user model. Plinta references `settings.AUTH_USER_MODEL` and `get_user_model()` and never defines a user.

The `accounts` app dissolves:

- the user model is **deleted**
- `UserCompanyAccess` / `UserBusinessUnitAccess` move to `contrib.organization` — they are organisation concepts that reference a user, not user concepts
- the permission console moves to **core**, where it operates on Django's own `auth.Permission` and `auth.Group`

#### Consequences

Plinta installs into an existing project without touching its authentication. Migrations use `swappable_dependency`; foreign keys use string references.

The permission console works with any user model, because it never touches one — it manages Django's permissions and groups.

Contributors must resist adding a field to "the user". There is no user to add a field to. Anything that looks like user data belongs to the app that needs it, attached by foreign key or generic relation.

#### Migration note

For an existing deployment this is the most disruptive decision in the set: it means retiring a live `AUTH_USER_MODEL`. It is nevertheless the right default for a library, and the cost is paid once.

### ADR 0003 — Contrib interacts through a core event bus

**Status:** accepted, 2026-08-28

#### Context

Optional apps called each other directly. `comments`, `actions`, `workflow` and the core write pipeline all imported `notifications.triggers`; the kanban component imported `labels.models` at module scope; the write pipeline imported `audit.services` at two points in its hottest path.

Each import made an optional app mandatory. Guarding them with `apps.is_installed()` would have hidden the coupling rather than removed it — and lazy importing does not help, because a deferred import of a model from an uninstalled app still fails.

#### Decision

Core owns a signal bus. Emitters emit; listeners subscribe. **No contrib package imports another.**

Five signals: `object_writing`, `object_written`, `object_deleted`, `state_changed`, `comment_posted`. All five are declared in core, including the two that contrib emits — a signal is a vocabulary, not a schema, and declaring `state_changed` requires no `Workflow` model.

`object_written` carries `changes` as `{field: (before, after)}`, **computed by core**.

#### Why core computes the diff

This is the load-bearing part.

Audit writes one row per changed field, which needs a pre-save baseline. If audit had to take that snapshot itself it would need a hook inside the write pipeline and would not be a listener.

It does not, because **core performs the write and already knows what changed.** Computing the diff is a statement about the write, not a service rendered to audit. Notifications reads the same payload; labels reads the label field from it.

That audit — the app most deeply embedded in core's write path — reduced to a pure listener with no widening of the vocabulary is the evidence the model is right. Had it needed a seventh signal or a pipeline hook, the model would have been wrong.

#### Consequences

Every sideways import is deleted structurally rather than guarded.

Handlers are synchronous, must not raise, and are logged and swallowed if they do. A failed audit row or notification must never fail a user's save. Ordering between listeners is undefined. Emission is skipped when a signal has no receivers, so diff computation costs nothing on a minimal install.

A consumer with its own state machine can emit `state_changed` and get audit and notification coverage without installing `contrib.workflow`.

#### What the bus does not cover

The bus inverts **behavioural** coupling only. Two other kinds exist and are declared instead (§2.5):

`enhances` — a functional call into another package, which must name a substitute with the same interface. They are registered in §2.5.

`composes` — a structural dependency: a base class, a `ForeignKey`, a migration `dependencies` entry. It cannot degrade, so it is a boot error, exactly as `django.contrib.flatpages` depends on `sites`. No shipped package declares one.

**Revised 2026-08-29.** This ADR originally read as though the bus made cross-contrib dependency unnecessary in general. It does not, and `django.contrib` is the counter-example: `admin` imports four sibling apps at module scope and checks for them at boot. The bus removes the couplings that *should* be events. Declaring the rest is not a failure of the design.

### ADR 0004 — Personalisation leaves the rendering layer

**Status:** accepted, 2026-08-28

#### Context

A component resolved its own effective configuration by merging the block's config with the current user's saved-view delta. Personalisation therefore lived inside the rendering layer.

The cost was visible but had been misread as a DRY failure: five components each carried a near-identical save-payload parser, seven `view_config` modules were one-line aliases, and view-CRUD endpoints were generated per component type — roughly 250 lines of duplication.

#### Decision

The component contract is **config in, HTML out**. A component receives an already-resolved configuration and never merges anything.

Resolution moves one layer up, into `blocks`. `PageFilter` — the filter *bar* — is composition and belongs to `pages`.

`SavedView` and `FilterSet` ship together because they are the same species: user-owned, shareable, a delta over a shared base, stored and resolved identically.

#### Consequences

The duplication disappears with the layer that caused it. It was never repetition to be factored out — it was the shape of a misplaced responsibility, which is why previous attempts to tidy it found nothing worth extracting.

Components become simpler and independently testable: given a config, assert the HTML.

**Revised 2026-08-29 — the packaging half is reversed.** This ADR did two things: it moved the *merge* out of components, and it moved the *models* to contrib. The first stands and is the whole point. The second was wrong. All three tests (§2) put them in core; the mistake was applying the sentence test to a paraphrase — "core can render a screen without them" — when the sentence promises *interactive* screens, and a screen that forgets how a user arranged it is not interactive. The optionality was fiction: personalisation is not a feature a dashboard platform can ship without and still be one. `SavedView` lives in `blocks`, `FilterSet` and `PageFilterPreference` in `pages` — each with the thing it is a delta over. The hook disappears with the optionality; `blocks` merges directly. See §14.3a.

The component contract is unaffected either way, which is what made the two decisions separable in the first place.

Deltas remain deltas, never copies. A saved view stores only what differs, so a change to the underlying block reaches every view except where one deliberately overrides. Storing full copies would fork configuration silently.

### ADR 0005 — Core ships `table_plinta` and no other component

**Status:** accepted, 2026-08-28

#### Context

Core bundled ten component types. Each carried a config schema, a template, static assets, an API router and, for three of them, a front-end vendor: Plotly, Flexmonster, jsGantt.

Bundled components registered through `AppConfig.ready()` — nominally the same path a third party would use, but core enumerated them, so the path was never actually tested from outside.

#### Decision

Core ships the component contract, the registry, and **`table_plinta`** as the reference implementation. Everything else — every other entry in §11's catalogue, including the interactive `table_tabulator` — becomes an independently installable contrib package.

A Block referencing an unregistered component type renders as an **empty slot**. This is a normal state, not an error.

#### Rationale

Adding a component is the only extension anybody would realistically write — including this project, the next time a consumer needs a new visualisation. If bundled components had a private path into the registry and third parties a public one, only the private path would stay working. Routing every component through the public door makes the contract true by construction rather than by intention.

#### Consequences

Front-end vendors ship with their components, and core carries neither a CSS framework nor a grid library. So core absorbs no front-end major-version upgrade: Tabulator, Plotly, Flexmonster and jsGantt all become the concern of whoever installs the component that carries them.

**Trade accepted:** core alone composes a detail page but renders a record as a single-row table until `contrib.components.details_card` is installed. `details-card` was the strongest candidate to keep in core and was excluded to keep the rule absolute — one reference implementation, no exceptions.

Removing a component degrades pages rather than breaking them, which makes uninstalling one safe.

### ADR 0006 — Tenancy is a provider, not a dependency

**Status:** accepted, 2026-08-28

#### Context

`permissions` knew about organisations by name: its scoping module referenced Company, Site and BusinessUnit directly, and structural scoping was written in terms of that hierarchy.

The organisation app was also foundational for an unrelated reason — four core-level modules imported its fiscal and relative-date helpers at module scope. That single import chain was the only thing keeping a manufacturing-ERP organisation hierarchy mandatory in a platform that has no notion of a factory.

#### Decision

The permission engine ships only generic rules (eleven, §5.4). Four carry the access model — `Owner`, `Public`, `InstancePerm`, and `FieldInUserSet`, the abstract shape of structural scoping. `FieldInUserSet` knows a field name and how to derive a permitted set from a user; it does not know what the field points at.

`contrib.organization` binds those rules to a concrete hierarchy and registers the resulting policies. **The engine never imports the provider.**

The date helpers split: calendar arithmetic (`last_30_days`, `current_month`) is core `dates`; the fiscal calendar is `contrib.organization`, which registers its named ranges into core's resolver.

#### Consequences

A single-tenant project installs no organisation app and still has ownership, public/private, per-instance sharing and field-level permissions — a complete access model.

A project whose tenancy is a `Portfolio`, a `Desk` or a `Household` writes one provider and gets identical scoping. `contrib.organization` is one provider, not the provider.

Fiscal options appear in filter UIs only when the app defining them is installed — the first and simplest instance of the general pattern: core owns the contract and the generic implementations, contrib adds domain-specific ones through the same door. Needing a core change to register a fiscal range would prove the pattern wrong.

This is also the decision that removes the last structurally ERP-shaped assumption from core. The inherited vocabulary was cleaned out of the source earlier; this removes it from the *schema*, which is where it actually lived.

### ADR 0007 — Two API surfaces

**Status:** accepted, 2026-08-28

#### Context

Plinta had 81 django-ninja endpoints behind session auth. **46 of them returned HTML fragments** for HTMX, marked `include_in_schema=False`, so the published OpenAPI spec described 43% of the surface. Read endpoints deliberately returned unenveloped shapes, documented as stable contracts with frontend widgets — Tabulator, TomSelect, htmx.

It was not an API. It was an RPC transport for plinta's own frontend, wearing OpenAPI clothes — which was the right thing to build, and which cannot also serve a partner: the moment an external client depends on a shape, the frontend cannot change it.

There was also a concrete defect. Ninja owning a fragment path answers an unauthenticated request with a JSON `401`, which HTMX swaps into the page. The escape used was `auth=None` on `notifications/preferences/`, leaving that endpoint's safety dependent on the *consuming project's* `LoginRequiredMiddleware`.

#### Decision

**Two surfaces, separated by contract.**

**Public data API** — django-ninja, versioned, fully specified, generated from the DataSource registry. Seven generic handlers serve every registered model; there is no per-model API code. Authentication by API key or session; a key resolves to a user.

**Private UI transport** — plain Django views with `@login_required`, per-app URLconfs, no version, no spec, no stability promise.

**Permissions are the only gate.** No publish flag on DataSource, no field-level API flag. `view_{model}` and `view_{model}_{field}` already answer both questions, and every entry point filters — the listing by model permission, the schema by `get_available_fields`, the rows by `get_queryset`.

#### Rejected alternatives

**A publish flag per DataSource.** Argued for on schema-disclosure and stability grounds; both failed.

> **Revised 2026-08-28 — the flag is reinstated as `show_in_api`, default `False`.** Not for the reasons rejected here, which still stand: every entry point is permission-filtered, so an unentitled caller learns nothing either way. It returns on **curation** grounds. Plinta's own models are registered as DataSources so DSF-driven field permissions cover them (§5.7), which would otherwise publish `SavedView`, `PageBlock`, `EmailQueue` and their kin as stable API resources. It is surface curation, not access control. See §6.1a.
 Disclosure fails because a permission-filtered listing already returns nothing to an unprivileged caller — the argument assumed a public listing. Stability is real but is an argument for versioning and deprecation policy, not a per-resource toggle. Frappe exposes every DocType and Directus every collection, both gated purely by permissions.

**A field-level API flag.** A second mechanism answering the question field permissions already answer, and therefore a second mechanism that drifts. Per-key field visibility is achieved by minting the key against a service user with a restricted role.

**Keeping fragments on ninja.** Preserves one routing system at the cost of a spec that describes 43% of the surface, a workaround that outsources authentication to consumer middleware, and `include_in_schema=False` discipline forever.

#### Consequences

The spec describes 100% of the public surface. `auth=None` disappears, and with it plinta's dependence on a consumer's middleware for its own auth.

An API write goes through the block write pipeline, so it is authorised, validated, audited and notified exactly like a UI edit — no second write path.

`reverse()` splits across namespaces: `api:` for JSON, per-app namespaces for fragments. This is the accepted cost. It is not a new routing system — `plinta/urls.py` already existed as a deprecation-targeted `reverse()` shim, and stops being deprecated.

`contrib.api` is optional: a machine-to-machine API is not needed to turn models into screens.

Every registered DataSource becomes a public resource. Adding a dashboard column therefore changes the published API, which is why breaking changes require a new version rather than an edit.

---

### ADR 0008 — `actions` is a consumer app, not a contrib package

**Status:** accepted 2026-08-29; reasoning revised the same day (see *Revision*).

**Context.** `contrib.actions` shipped a task tracker: `Action`, `Urgency`, reminders, blocking, followers, an inline row extension. 1,900 lines and five templates.

It carried the project's only structural cross-contrib dependency. `Action` inherits `WorkflowMixin`, holds two `ForeignKey`s into workflow's tables, and its migration declares `dependencies = [('workflow', '0001_initial')]`.

**Decision.** `actions` is **not shipped**. It is deleted from plinta together with `Urgency`, the `/actions-inline/` endpoint, the three `plinta/partials/action*.html` templates, the assignment email, and `seed_actions_page`. Anyone wanting task tracking builds it as a consumer app.

**Why — the facility/domain line.** Plinta ships facilities, not domains. `comments`, `labels`, `attachments` and `checklist` are domain nouns too, and they stay, because every application wants to attach a note or a file to a record. `Action` as built is not that shape: `responsible`, `assigned_to`, `urgency`, `followers`, `blocked_by`, `recipient_roles`, escalating reminders. That is one organisation's corrective-action process, and it is the largest surviving piece of the codebase's origin.

Three supporting facts:

- `WorkflowMixin` has exactly **one** subclass in the entire codebase — `Action`. A mixin designed for reuse and used once is speculative generality.
- `Urgency` sits in `plinta/core/models.py`. It is `Action`'s lookup and a domain noun in core, which the noun test forbids.
- `blocks/api.py` imports `Action` at module scope for one endpoint, making a task tracker mandatory for anyone rendering a table.

**Why a consumer app is the right home.** `example/catalog` already is one: plain Django models that import `WorkflowMixin` from outside plinta and drive datasources, filters, pivots, capabilities, reports and org-scoped permissions. This is ADR 0005 applied above the component layer — core ships one component and no other so the plugin door is real; plinta ships no domain app so the **consumer** door is real. If a task tracker cannot be built on the published API from outside, the API is fiction.

**Consequences.**

- `core` holds no domain nouns.
- `workflow` keeps a consumer — `example/catalog` — so it is not shipped untested.
- Four test modules (`accounts`, `audit`, `workflow`, `notifications`) use `Action` as a convenient workflow-enabled fixture. Each gains a local test model, which removes three apparent contrib→contrib cycles that were never runtime dependencies.
- Two mechanisms lose their only shipped consumer: page `tabs` and the `__CURRENT_USER__` create-default. Both are kept on the strength of the mechanism; §21 records that their usage count is now zero.
- ~1,900 lines of Python and five templates leave the repository.

**Revision — 2026-08-29.** This ADR originally argued that the `WorkflowMixin` dependency *could not be permitted*, because no event bus inverts a base class or a migration dependency. That premise was wrong, and checking `django.contrib` is what showed it: `flatpages` holds a `ForeignKey` to `sites.Site` and a migration dependency on it, and `admin` imports four sibling apps at module scope. Django's rule is that such a dependency be **declared and checked**, not that it be absent. §2.5 now says the same, and `composes` is the declaration for exactly this shape.

So `actions` **could** have shipped as contrib declaring `composes: workflow`. The decision not to stands on the facility/domain argument above, which never depended on the layering rule.

An earlier draft of §14 also claimed `Action` "uses `WorkflowMixin` when `contrib.workflow` is installed and falls back to a plain status field otherwise… guarded and degrading." No such fallback exists in the code. That sentence is recorded here because it is the failure mode the `enhances` contract now guards against: a dependency described as optional because describing it that way preserved a rule. An `enhances` relationship must **name its substitute** (§2.5), and a claim of degradation that cannot name one is false.

**What this does not mean.** Contrib packages may still be domain-shaped, and may still declare `composes` on one another. The test is not "is it domain?" but "does every application want it?" `actions` did not.

---

## 25. Skills



A skill is the **executable half of this document**. The spec says what a thing *is*; a skill says how to *add one*. Every extension point in §18 should have one, because an extension point nobody can follow is a contract in name only.

### 25.1 One skill per extension point

| Extension point | Skill | Owning layer |
|---|---|---|
| `register_placeholder` | `add-placeholder` | utils (§3.6) |
| `register_range` | `add-date-range` | dates (§3.2) |
| `register_widget` | `add-widget-override` | forms (§3.3) |
| event listener (`@receiver`) | `add-event-listener` | events (§4) |
| `register_policy` | `add-policy` | permissions (§5) |
| a rule | `add-rule` | permissions (§5) |
| `register_queryset_modifier` | `add-queryset-modifier` | datasources (§6) |
| `register_annotation` | `add-computed-column` | datasources (§6) |
| `register_renderer` | `add-renderer` | renderers (§7) |
| `register_field_renderer` | `add-field-renderer` | renderers (§7) |
| `register_component` | `add-component` | components (§7) |
| `register_capability` | `add-capability` | blocks (§8) |
| a contrib package | `add-contrib-app` | contrib (§14) |
| a consumer application | `start-consumer-app` | the whole surface (§1.4) |

Fourteen points, fourteen skills. `add-component` and `start-consumer-app` are the two that will be used most. `start-consumer-app` is the widest: it registers a plain Django model as a DataSource, declares a policy over it, and seeds a page — the shortest path from "I have models" to "I have screens", written only against the public API.

### 25.2 Examples use the demo domain

Every skill, and every example in this document, draws its nouns from
`example/catalog` — the bookshop chain: `Book`, `Sale`, `PurchaseOrder`,
`Promotion`, over stores and regions.

A reader who has never seen plinta understands a book and an order. They do not
understand an instrument, a watchlist or a work order, and an example written in
one consumer's vocabulary reads as though plinta were built for that consumer.
This is the same reason plinta ships no domain application (§1.4): the moment
the documentation speaks one tenant's language, that tenant stops being a
consumer.

The domain is fixed now and used from the first skill, though `example/catalog`
itself is ported last (§23.4) — the vocabulary costs nothing to settle early and
everything to change late.

### 25.3 A skill is written with its layer, never before

A skill written against a layer that does not exist yet is fiction. §21 records four documented behaviours the code never had, and a skill is documentation that people follow *more* literally than prose — so the failure mode is worse.

So: a layer is not done until its extension points have skills, and a skill is not written until the layer is.

### 25.4 The v1 skills are not ported

Sixteen exist today — `add-block-type`, `setup-datasource`, `add-workflow` and the rest. They encode v1 structure: module paths that move, the `AJAX` class constant that becomes a mode, model-driven field permissions that become DSF-driven, `is_staff` gates that become permissions.

**Re-derive each from its spec section; do not port it.** This is the same rule §21 sets for documentation — behaviour is established from the spec and the code, never carried over from prose that was written against something else.

The old skills stay readable in git history for reference, exactly as the v1 code does.

### 25.5 A skill and its section change together

If §7.2's component contract changes, `add-component` changes **in the same commit**. A skill that lags its section is worse than no skill, because it is confidently wrong.

This is the same coupling the design applies elsewhere: permissions follow the column, adapters ship with their components, vendors ship with the package that needs them.

### 25.6 Section-by-section, as we go

The document is updated **as each layer is built**, not afterwards:

1. Specify the section.
2. Build the layer against it.
3. Update the section to match what was actually built — including its `Must not know` line.
4. Write the skills for its extension points.
5. Resolve its §21 ledger rows.

Steps 3–5 are part of §23's definition of done, not follow-up work. Where the built code and the section disagree, one of them is wrong and it is decided before moving on — the disagreement is the signal, and deferring it is how a spec becomes fiction.

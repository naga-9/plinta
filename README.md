# plinta

[![CI](https://github.com/naga-9/plinta/actions/workflows/ci.yml/badge.svg)](https://github.com/naga-9/plinta/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A reusable Django platform for building data-driven business apps. It provides the
plumbing so a consuming project only has to describe its screens as data:

- **DataSources / DataSourceFields** — register any Django model for the dashboard and
  declare per-column display, filtering, and inline-edit behavior.
- **Blocks** — typed, config-validated visualizations (table, chart, pivot, kpi, gauge,
  kanban, gantt, details-card, alert, text) bound to a DataSource.
- **Pages** — arrange Blocks on a 12-column grid with a filter bar; menu-driven navigation.
- **Components** — the block-type registry; extend it with new visualization types.
- **Permissions** — declarative row-level `PermissionPolicy` subclasses; field-level perms
  auto-generated.
- **Workflow + Audit** — DB-backed state machine with per-transition guards, plus a generic
  audit log (state + transition-event history).
- **Notifications, Comments, Labels, Attachments** — cross-cutting mixins via GenericRelation.

The `/api/v1` layer is built on django-ninja + pydantic; the frontend uses HTMX.

## Install

Editable, for local development alongside a consuming project:

```
pip install -e ../plinta
```

Or from git (no release is tagged yet, so pin to a branch or commit; once a
version is tagged, pin to the tag for reproducible/prod installs):

```
plinta @ git+https://github.com/naga-9/plinta.git@main
```

PDF export (pages/reports) is optional and needs GTK native libraries:

```
pip install -e "../plinta[pdf]"
```

## Consuming project setup

A minimal, verified reference configuration lives in `tests/settings.py` and
`tests/urls.py` — copy from there. The steps below spell it out.

### 1. `INSTALLED_APPS`

List `plinta` (the root AppConfig) **before** `django.contrib.admin` so its
admin-template overrides win, then the sub-apps you use, plus `django_ckeditor_5`:

```python
INSTALLED_APPS = [
    "plinta",              # root AppConfig — BEFORE django.contrib.admin
    "plinta.core",
    "plinta.accounts", "plinta.organization", "plinta.permissions",
    "plinta.workflow", "plinta.audit", "plinta.datasources",
    "plinta.blocks", "plinta.components", "plinta.pages", "plinta.filters",
    "plinta.actions", "plinta.projects", "plinta.tickets", "plinta.checklist",
    "plinta.comments", "plinta.labels", "plinta.attachments",
    "plinta.notifications", "plinta.reports", "plinta.scheduling",
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "django_ckeditor_5",
]

AUTH_USER_MODEL = "accounts.CustomUser"   # plinta ships its own user model
```

### 2. URLs

Mount the ninja API **before** `plinta.urls`. Both the `plinta:` (auth) and
`plinta:` (pages/reports/reverse) namespaces are required by shipped templates:

```python
from plinta.api import api as plinta_api

urlpatterns = [
    path("api/v1/", plinta_api.urls),          # /api/v1/..., /docs, /openapi.json
    path("ckeditor5/", include("django_ckeditor_5.urls")),
    path("", include("plinta.urls")),          # namespace: plinta  (+ /pages/, /reports/)
    path("", include("plinta.auth_urls")),     # namespace: shell   (login/logout/home)
]
```

### 3. Middleware & templates

Standard Django middleware plus `AuthenticationMiddleware`. plinta expects a
login-gated site, so add `LoginRequiredMiddleware` (its own login / password-reset
views are `login_not_required`). Templates need `APP_DIRS: True` and three context
processors (fully qualified):

```python
"context_processors": [
    "django.template.context_processors.request",
    "django.contrib.auth.context_processors.auth",
    "django.contrib.messages.context_processors.messages",
    "plinta.context_processors.menu_pages",
    "plinta.context_processors.pivot_provider_settings",
    "plinta.context_processors.deployment_env",
],
```

### 4. Required settings

plinta reads these via `getattr(settings, ...)` — most degrade gracefully, but
define them explicitly:

| Setting | Purpose |
|---|---|
| `STATUS` | Deployment badge shown in the topbar (e.g. `"PROD"`). |
| `TOPBAR_COLOR` | Topbar background colour. |
| `FLEXMONSTER_LICENSE_KEY` | Flexmonster pivot licence (empty = trial). |
| `DEFAULT_FROM_EMAIL` | Sender for notification / scheduled-report emails. |
| `ATTACHMENT_BUCKETS` | Attachment storage buckets (`{}` = none registered). |
| `ATTACHMENT_ALLOWED_EXTENSIONS` / `ATTACHMENT_MAX_SIZE_MB` / `ATTACHMENT_MAX_PER_INSTANCE` | Attachment upload limits (have built-in defaults). |
| `CKEDITOR_5_CONFIGS` | Must define at least `default` and `comment` toolbars. |

### 5. Migrate & seed

Run `migrate`, then seed platform config (DataSources / Blocks / Pages /
Workflows) via your project's own setup command.

### Front-end assets

Vendor CSS/JS (Bootstrap, Tabulator, HTMX, Plotly, Flexmonster, CKEditor, fonts)
are loaded from CDNs in `templates/plinta/base.html`. An offline / strict-CSP
deployment must vendor these into `static/` and adjust the base template.

## License

MIT — see [LICENSE](LICENSE).

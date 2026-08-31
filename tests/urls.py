"""URLs for plinta's own suites. A consuming project supplies its own."""
from django.apps import apps
from django.contrib import admin
from django.urls import include, path

# Mounted so each app's admin.py is exercised rather than merely imported: a
# broken inline passes the system checks and raises when the form is built.
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("plinta.shell.urls")),
]

# Contrib mounts its own URLs, and only when installed. Guarded on the app
# registry rather than on ImportError: importing a module whose models belong
# to an uninstalled app raises RuntimeError, not ImportError, so a try/except
# around the import would let that through.
if apps.is_installed("plinta.contrib.notifications"):
    urlpatterns += [
        path("notifications/", include("plinta.contrib.notifications.urls")),
    ]

if apps.is_installed("plinta.contrib.workflow"):
    urlpatterns += [path("workflow/", include("plinta.contrib.workflow.urls"))]

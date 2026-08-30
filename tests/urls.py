"""URLs for plinta's own suites. A consuming project supplies its own."""
from django.apps import apps
from django.urls import include, path

urlpatterns = [path("", include("plinta.shell.urls"))]

# Contrib mounts its own URLs, and only when installed. Guarded on the app
# registry rather than on ImportError: importing a module whose models belong
# to an uninstalled app raises RuntimeError, not ImportError, so a try/except
# around the import would let that through.
if apps.is_installed("plinta.contrib.notifications"):
    urlpatterns += [
        path("notifications/", include("plinta.contrib.notifications.urls")),
    ]

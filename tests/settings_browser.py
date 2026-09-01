"""Settings for the browser suite.

Contrib's, because the thing under test is a component that fetches and
`table_tabulator` is the one that does. Run separately:

    pytest -c pytest-browser.ini
"""
import os

from tests.settings_contrib import *  # noqa: F403

# Playwright's sync API runs the test body inside a greenlet with an event
# loop running, and Django refuses synchronous database work there. The guard
# is protecting against blocking an async caller's loop; here the loop belongs
# to the browser driver and nothing else is waiting on it, so the risk it
# names does not exist.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

# The live server serves static files from the apps, the way a deployment
# serves them from a collected root. Without this the client never loads and
# every test here fails for a reason that has nothing to do with the client.
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

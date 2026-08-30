"""Settings for plinta's own suite. A consuming project supplies its own."""
SECRET_KEY = "test-only-not-a-secret"  # noqa: S105
USE_TZ = True

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "plinta.permissions",
    "tests.testapp",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

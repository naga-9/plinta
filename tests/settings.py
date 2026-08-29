"""Minimal settings so plinta's own suite can run without a consuming project."""
SECRET_KEY = "test-only-not-a-secret"  # noqa: S105
USE_TZ = True
DATABASES = {}
INSTALLED_APPS = []

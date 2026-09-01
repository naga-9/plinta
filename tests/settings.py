"""Settings for core's own suite. A consuming project supplies its own.

**No contrib app is installed here.** One that connected a receiver would
change what a core test observes — `has_listeners` was the first to notice —
and a core suite that depends on a contrib package being present is the
coupling this architecture exists to prevent. Contrib has its own settings.
"""
SECRET_KEY = "test-only-not-a-secret"  # noqa: S105
USE_TZ = True

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "plinta.permissions",
    "plinta.datasources",
    "plinta.renderers",
    "plinta.components",
    "plinta.blocks",
    "plinta.pages",
    "plinta.shell",
    "tests.testapp",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ROOT_URLCONF = "tests.urls"
STATIC_URL = "/static/"

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    # A deployment runs it and the write endpoint depends on it, so the suite
    # runs it too. The test client does not enforce it unless asked; the
    # browser suite makes real requests and does.
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "plinta.shell.middleware.LoginRequiredMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "plinta.shell.context_processors.branding",
                "plinta.shell.context_processors.styles",
                "plinta.shell.context_processors.menu",
            ]
        },
    }
]

"""Settings for plinta's own suite. A consuming project supplies its own."""
SECRET_KEY = "test-only-not-a-secret"  # noqa: S105
USE_TZ = True

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
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
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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
                "plinta.shell.context_processors.branding",
                "plinta.shell.context_processors.menu",
            ]
        },
    }
]

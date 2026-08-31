"""The demo project.

An ordinary Django project that installs plinta. Nothing here is privileged:
everything `catalog` does, a third party can do (§18.14).
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "demo-only-not-a-secret"  # noqa: S105
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    # Not required by plinta, and not how the demo is meant to be used: every
    # screen here is a plinta Page. It is installed so `root` has somewhere to
    # edit users and groups directly.
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # plinta, layer by layer
    "plinta.permissions",
    "plinta.datasources",
    "plinta.renderers",
    "plinta.components",
    "plinta.blocks",
    "plinta.pages",
    "plinta.shell",
    # the consumer
    "catalog",
    # The project itself, so its admin.py is autodiscovered like any other.
    "demo",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # After AuthenticationMiddleware, which is what the boot check verifies.
    "plinta.shell.middleware.LoginRequiredMiddleware",
]

ROOT_URLCONF = "demo.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "demo" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "plinta.shell.context_processors.branding",
                "plinta.shell.context_processors.menu",
            ]
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "demo.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "en-us"
USE_TZ = True
STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

PLINTA_SITE_NAME = "Marginalia Books"

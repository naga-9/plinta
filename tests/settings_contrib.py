"""Settings for the contrib suite.

Core's settings plus every contrib package, because a contrib test needs its
own models and its receivers connected. Run separately:

    pytest -c pytest-contrib.ini
"""
from tests.settings import *  # noqa: F403

INSTALLED_APPS = [  # noqa: F405
    *INSTALLED_APPS,  # noqa: F405
    "plinta.contrib.audit",
    "plinta.contrib.notifications",
    "plinta.contrib.comments",
    "plinta.contrib.workflow",
    "plinta.contrib.styles_bootstrap5",
    "plinta.contrib.filters_tomselect",
    "plinta.contrib.components.table_tabulator",
    "plinta.contrib.composer",
    "tests.contribapp",
]

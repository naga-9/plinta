"""Settings for the contrib suite.

Core's settings plus every contrib package, because a contrib test needs its
own models and its receivers connected. Run separately:

    pytest -c pytest-contrib.ini
"""
from tests.settings import *  # noqa: F403

INSTALLED_APPS = [  # noqa: F405
    *INSTALLED_APPS,  # noqa: F405
    "plinta.contrib.audit",
]

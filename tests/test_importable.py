"""Every package must import before ``django.setup()``.

A library that imports models at module scope cannot be imported while the app
registry is still populating — which is exactly when a consumer's
``AppConfig.ready()`` runs. The failure is an ``AppRegistryNotReady`` a long
way from its cause, so it is cheaper to forbid the import than to debug it.

Run in a subprocess, because this process has Django configured already.
"""
import os
import subprocess
import sys

import pytest

PACKAGES = [
    "plinta",
    "plinta.utils",
    "plinta.dates",
    "plinta.forms",
    "plinta.events",
    "plinta.permissions",
    "plinta.datasources",
    "plinta.renderers",
]


@pytest.mark.parametrize("package", PACKAGES)
def test_imports_with_no_settings_configured(package):
    env = {k: v for k, v in os.environ.items() if k != "DJANGO_SETTINGS_MODULE"}
    result = subprocess.run(
        [sys.executable, "-c", f"import {package}"],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    assert result.returncode == 0, (
        f"{package} needs Django configured to import:\n"
        f"{result.stderr.strip().splitlines()[-1] if result.stderr else ''}"
    )

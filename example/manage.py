#!/usr/bin/env python
"""The demo project's entry point.

Runnable straight from a clone: the repository root goes on the path first, so
`python manage.py runserver` works with only Django installed, and picks up the
plinta beside it rather than any other copy on the machine.

A real consumer does not do this — they `pip install plinta-core` and their
manage.py is Django's own.
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demo.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)

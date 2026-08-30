"""Every model change must arrive with its migration."""
from io import StringIO

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_no_missing_migrations():
    """`makemigrations --check` is the whole test.

    A model edited without a migration passes every other test in the suite and
    fails on a consumer's next deploy.
    """
    out = StringIO()
    try:
        call_command("makemigrations", "--check", "--dry-run", stdout=out, stderr=out)
    except SystemExit:
        pytest.fail(f"a model has changed without a migration:\n{out.getvalue()}")

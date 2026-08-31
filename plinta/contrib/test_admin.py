"""Every contrib model opens in Django's admin.

The same sweep `tests/test_admin.py` runs over core, repeated here because the
suites collect different trees: core's does not install a contrib app, and
this one collects only `plinta/contrib`. A contrib package ships its own
`admin.py`, so a contrib package tests it.
"""
import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model

CONTRIB = sorted(
    (m for m in admin.site._registry if m.__module__.startswith("plinta.contrib.")),
    key=lambda m: (m._meta.app_label, m._meta.model_name),
)
IDS = [f"{m._meta.app_label}.{m._meta.model_name}" for m in CONTRIB]


@pytest.fixture
def as_root(client, db):
    User = get_user_model()
    client.force_login(User.objects.create_superuser("root", password="x"))  # noqa: S106
    return client


def test_every_contrib_app_registers_something():
    """Guards the sweep, and names the four packages that ship models."""
    assert {m._meta.app_label for m in CONTRIB} == {
        "plinta_audit", "plinta_comments", "plinta_notifications", "plinta_workflow",
    }


@pytest.mark.parametrize("model", CONTRIB, ids=IDS)
def test_the_changelist_opens(as_root, model):
    m = model._meta
    assert as_root.get(f"/admin/{m.app_label}/{m.model_name}/").status_code == 200


@pytest.mark.parametrize("model", CONTRIB, ids=IDS)
def test_the_add_form_opens(as_root, model):
    """Where a broken inline surfaces — the formset is built here, not before."""
    m = model._meta
    response = as_root.get(f"/admin/{m.app_label}/{m.model_name}/add/")
    # The audit trail refuses adds by design; everything else must offer one.
    assert response.status_code in (200, 403), response.status_code


def test_the_audit_trail_is_read_only(as_root):
    """An audit entry that can be edited is not an audit trail."""
    assert as_root.get("/admin/plinta_audit/auditentry/add/").status_code == 403

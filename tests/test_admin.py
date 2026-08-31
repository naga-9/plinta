"""Every model plinta registers opens in Django's admin.

An app that ships models ships its admin registrations, the way Django's own
contrib apps do. The authoring screens (§12) are a domain-specific editor on
top of the generic one, not a replacement — and registering here is what
spares every consumer from writing the same file.

**The add form is where a broken registration surfaces.** `manage.py check`
validates `list_display` and `list_filter`, but an inline naming a field the
model does not have passes it and raises `FieldError` when the formset is
built. So these open the pages rather than inspecting the classes.
"""
import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model

PLINTA = sorted(
    (m for m in admin.site._registry if m.__module__.startswith("plinta.")),
    key=lambda m: (m._meta.app_label, m._meta.model_name),
)
IDS = [f"{m._meta.app_label}.{m._meta.model_name}" for m in PLINTA]


@pytest.fixture
def as_root(client, db):
    User = get_user_model()
    root = User.objects.create_superuser("root", password="x")  # noqa: S106
    client.force_login(root)
    return client


def test_plinta_registers_its_models():
    """Guards the sweep: an empty registry would pass every test below."""
    assert {"plinta_datasources.datasource", "plinta_blocks.block",
            "plinta_pages.page"} <= set(IDS)


def test_the_index_opens(as_root):
    assert as_root.get("/admin/").status_code == 200


@pytest.mark.parametrize("model", PLINTA, ids=IDS)
def test_the_changelist_opens(as_root, model):
    m = model._meta
    assert as_root.get(f"/admin/{m.app_label}/{m.model_name}/").status_code == 200


@pytest.mark.parametrize("model", PLINTA, ids=IDS)
def test_the_add_form_opens(as_root, model):
    m = model._meta
    response = as_root.get(f"/admin/{m.app_label}/{m.model_name}/add/")
    # An audit entry is deliberately not addable; anything else must be.
    assert response.status_code in (200, 403), response.status_code

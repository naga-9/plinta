"""Every registered admin page opens.

`manage.py check` does not catch all of this. An inline naming a field the
model does not have passes the system checks and raises `FieldError` when the
add form is built — so the only way to know the admin works is to open it.
"""
import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model

MODELS = sorted(admin.site._registry, key=lambda m: (m._meta.app_label, m._meta.model_name))
IDS = [f"{m._meta.app_label}.{m._meta.model_name}" for m in MODELS]


@pytest.fixture
def root(db):
    User = get_user_model()
    return User.objects.create_superuser("root-test", password="x")  # noqa: S106


@pytest.fixture
def as_root(client, root):
    client.force_login(root)
    return client


def test_the_models_are_registered():
    """Guards the sweep below: an empty registry would pass every test."""
    labels = set(IDS)
    assert {"catalog.book", "catalog.sale", "plinta_pages.page"} <= labels


def test_the_index_opens(as_root):
    assert as_root.get("/admin/").status_code == 200


@pytest.mark.parametrize("model", MODELS, ids=IDS)
def test_the_changelist_opens(as_root, model):
    m = model._meta
    assert as_root.get(f"/admin/{m.app_label}/{m.model_name}/").status_code == 200


@pytest.mark.parametrize("model", MODELS, ids=IDS)
def test_the_add_form_opens(as_root, model):
    """Where a broken inline surfaces — the formset is built here, not before."""
    m = model._meta
    assert as_root.get(f"/admin/{m.app_label}/{m.model_name}/add/").status_code == 200


def test_a_manager_is_refused(client, django_user_model):
    """The admin answers to is_staff, and a plinta role does not grant it."""
    mira = django_user_model.objects.create_user("mira-test", password="x")  # noqa: S106
    client.force_login(mira)
    response = client.get("/admin/", follow=True)
    assert "/admin/login/" in [url for url, _ in response.redirect_chain][-1]

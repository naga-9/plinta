"""The Data Sources screen: registering a model and managing its columns.

The one thing worth stating here, because it is easy to read as an oversight:
these are **configuration** models with no field permissions (§6.1b), so the
screen uses `ModelForm`s and ordinary model permissions rather than the write
pipeline. `authorise` would deny every field, because there is no field
permission to grant.
"""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.datasources.models import DataSource, DataSourceField
from plinta.shell.authoring import registerable
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db


def grant(user, model, *actions):
    ct = ContentType.objects.get_for_model(model)
    for action in actions:
        codename = f"{action}_{model._meta.model_name}"
        perm, _ = Permission.objects.get_or_create(
            codename=codename, content_type=ct, defaults={"name": codename}
        )
        user.user_permissions.add(perm)


@pytest.fixture
def author(db, client):
    user = User.objects.create_user(username="ada", password="secret")  # noqa: S106
    grant(user, DataSource, "view", "add", "change")
    grant(user, DataSourceField, "view", "add", "change", "delete")
    client.force_login(user)
    return user


@pytest.fixture
def books(db):
    return DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )


def test_the_list_needs_the_view_permission(client, db):
    nobody = User.objects.create_user(username="bob", password="secret")  # noqa: S106
    client.force_login(nobody)
    assert client.get("/data-sources/").status_code == 404


def test_the_list_shows_registered_models(client, author, books):
    body = client.get("/data-sources/").content.decode()
    assert "Books" in body
    assert f"/data-sources/{books.pk}/" in body


def test_registering_a_model_creates_a_source(client, author):
    response = client.post(
        "/data-sources/",
        {
            "content_type": ContentType.objects.get_for_model(Region).pk,
            "name": "regions",
            "label": "Regions",
            "description": "",
            "is_active": "on",
        },
    )
    created = DataSource.objects.get(name="regions")
    assert response.status_code == 302
    assert response.headers["Location"] == f"/data-sources/{created.pk}/"


def test_a_model_already_registered_is_not_offered_again(author, books):
    offered = {ct.pk for ct in registerable()}
    assert ContentType.objects.get_for_model(Book).pk not in offered
    assert ContentType.objects.get_for_model(Region).pk in offered


def test_the_form_hides_add_from_a_viewer(client, db, books):
    watcher = User.objects.create_user(username="eve", password="secret")  # noqa: S106
    grant(watcher, DataSource, "view")
    client.force_login(watcher)
    body = client.get("/data-sources/").content.decode()
    assert "Register a model" not in body


def test_the_model_cannot_be_changed_once_registered(client, author, books):
    body = client.get(f"/data-sources/{books.pk}/").content.decode()
    assert 'name="content_type"' not in body


def test_saving_details_renames_the_source(client, author, books):
    client.post(
        f"/data-sources/{books.pk}/",
        {"what": "source", "name": "books", "label": "Catalogue",
         "description": "", "is_active": "on"},
    )
    books.refresh_from_db()
    assert books.label == "Catalogue"


def test_adding_a_column_mints_its_field_permissions(client, author, books):
    client.post(
        f"/data-sources/{books.pk}/",
        {
            "what": "columns",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-field_name": "title",
            "form-0-label": "Title",
            "form-0-order": "0",
            "form-0-visible": "on",
            "form-0-editable": "on",
            "form-0-sorter": "string",
            "form-0-picker_mode": "auto",
        },
    )
    assert books.fields.filter(field_name="title").exists()
    # The column is the only thing that mints a field permission, and marking
    # it editable is what mints the change half (§5.7).
    codenames = set(
        Permission.objects.filter(
            content_type=ContentType.objects.get_for_model(Book)
        ).values_list("codename", flat=True)
    )
    assert {"view_book_title", "change_book_title"} <= codenames


def test_deleting_a_column_removes_it(client, author, books):
    column = DataSourceField.objects.create(
        data_source=books, field_name="title", label="Title"
    )
    client.post(
        f"/data-sources/{books.pk}/",
        {
            "what": "columns",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-id": str(column.pk),
            "form-0-field_name": "title",
            "form-0-label": "Title",
            "form-0-order": "0",
            "form-0-sorter": "string",
            "form-0-picker_mode": "auto",
            "form-0-DELETE": "on",
        },
    )
    assert not books.fields.filter(pk=column.pk).exists()


def test_a_viewer_without_change_cannot_write(client, db, books):
    watcher = User.objects.create_user(username="eve", password="secret")  # noqa: S106
    grant(watcher, DataSource, "view")
    client.force_login(watcher)
    client.post(
        f"/data-sources/{books.pk}/",
        {"what": "source", "name": "books", "label": "Hijacked",
         "description": "", "is_active": "on"},
    )
    books.refresh_from_db()
    assert books.label == "Books"


def test_the_screen_hints_the_models_own_fields(client, author, books):
    body = client.get(f"/data-sources/{books.pk}/").content.decode()
    assert 'id="pl-field-paths"' in body
    assert '<option value="title">' in body

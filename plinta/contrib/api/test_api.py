"""The public data API (§15).

Most of these are about one claim: **permissions are the only gate**, and
every entry point filters rather than just the row fetch. That is what makes
the absence of a field-level API flag safe, so it is what the tests are for.
"""
import json

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.contrib.api.models import ApiKey, digest
from plinta.datasources.models import DataSource, DataSourceField
from plinta.permissions.fields import sync_model
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db

BASE = "/api/v1/data/"


def grant(user, model, *codenames):
    content_type = ContentType.objects.get_for_model(model)
    for codename in codenames:
        permission, _ = Permission.objects.get_or_create(
            codename=codename, content_type=content_type, defaults={"name": codename}
        )
        user.user_permissions.add(permission)
    return User.objects.get(pk=user.pk)


@pytest.fixture
def books(db):
    source = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
        show_in_api=True,
    )
    DataSourceField.objects.create(
        data_source=source, field_name="title", label="Title",
        filterable=True, editable=True, order=0,
    )
    DataSourceField.objects.create(
        data_source=source, field_name="in_print", label="In print",
        filterable=True, order=10,
    )
    sync_model(Book, {"title": True, "in_print": False})
    return source


@pytest.fixture
def reader(db, books):
    user = User.objects.create_user(username="ada", password="secret")  # noqa: S106
    return grant(user, Book, "view_book", "view_book_title", "view_book_in_print")


@pytest.fixture
def rows(db, books, reader):
    north = Region.objects.create(name="North")
    for index in range(3):
        Book.objects.create(
            title=f"Book {index}", owner=reader, region=north,
            in_print=bool(index % 2),
        )
    return Book.objects.order_by("title")


def as_key(client, user):
    _, key = ApiKey.issue(name="test", user=user)
    client.defaults["HTTP_X_API_KEY"] = key
    return key


# --- authentication ---------------------------------------------------------


def test_an_anonymous_caller_is_401(client, books):
    assert client.get(BASE).status_code == 401


def test_a_key_authenticates_as_its_user(client, reader, rows):
    as_key(client, reader)
    body = client.get(f"{BASE}books/").json()
    assert body["total"] == 3


def test_the_plaintext_key_is_never_stored(db, reader):
    record, key = ApiKey.issue(name="test", user=reader)
    assert key not in json.dumps(
        list(ApiKey.objects.values("hashed", "hint", "name"))
    )
    assert record.hashed == digest(key)


def test_a_revoked_key_stops_working(client, reader, rows):
    key = as_key(client, reader)
    ApiKey.objects.filter(hashed=digest(key)).update(is_active=False)
    assert client.get(BASE).status_code == 401


def test_an_inactive_user_stops_working(client, reader, rows):
    """Disabling somebody is supposed to mean their keys stop too."""
    as_key(client, reader)
    User.objects.filter(pk=reader.pk).update(is_active=False)
    assert client.get(BASE).status_code == 401


def test_a_session_also_authenticates(client, reader, rows):
    client.force_login(reader)
    assert client.get(f"{BASE}books/").status_code == 200


# --- discovery must not reveal what access denies ---------------------------


def test_the_listing_is_filtered_by_the_model_permission(client, db, books):
    """An unprivileged caller learns no model or field names from it."""
    stranger = User.objects.create_user(username="eve", password="secret")  # noqa: S106
    as_key(client, stranger)
    assert client.get(BASE).json() == []


def test_the_listing_shows_what_the_caller_may_read(client, reader):
    as_key(client, reader)
    assert [item["name"] for item in client.get(BASE).json()] == ["books"]


def test_an_unpublished_datasource_is_absent_and_unreachable(client, reader, books):
    """`show_in_api` is curation, so unpublished is a 404 — a caller has no
    business learning that a DataSource exists but was not chosen."""
    as_key(client, reader)
    DataSource.objects.filter(pk=books.pk).update(show_in_api=False)
    assert client.get(BASE).json() == []
    assert client.get(f"{BASE}books/").status_code == 404


def test_the_schema_shows_only_fields_the_caller_may_see(client, db, books):
    seer = User.objects.create_user(username="sam", password="secret")  # noqa: S106
    seer = grant(seer, Book, "view_book", "view_book_title")
    as_key(client, seer)
    names = [f["name"] for f in client.get(f"{BASE}books/schema/").json()["fields"]]
    assert names == ["title"]


def test_a_row_omits_a_field_the_caller_may_not_see(client, db, books, rows):
    seer = User.objects.create_user(username="sam", password="secret")  # noqa: S106
    seer = grant(seer, Book, "view_book", "view_book_title")
    as_key(client, seer)
    row = client.get(f"{BASE}books/").json()["results"][0]
    assert "title" in row
    assert "in_print" not in row


# --- reading ----------------------------------------------------------------


def test_rows_are_the_raw_values_not_the_formatted_ones(client, reader, rows):
    as_key(client, reader)
    row = client.get(f"{BASE}books/").json()["results"][0]
    # A machine wants a boolean, not the word "No".
    assert row["in_print"] is False


def test_filtering_uses_the_lookup_the_column_implies(client, reader, rows):
    """A boolean filtered with `icontains` matches nothing and reads as "no
    rows" — the bug `kinds` exists to prevent."""
    as_key(client, reader)
    body = client.get(f"{BASE}books/?in_print=true").json()
    assert body["total"] == 1


def test_a_filter_on_an_invisible_column_is_ignored(client, db, books, rows):
    seer = User.objects.create_user(username="sam", password="secret")  # noqa: S106
    seer = grant(seer, Book, "view_book", "view_book_title")
    as_key(client, seer)
    # Not an error and not a narrowing: answering differently would say
    # whether the column exists.
    assert client.get(f"{BASE}books/?in_print=true").json()["total"] == 3


def test_ordering_by_an_invisible_column_is_ignored(client, db, books, rows):
    """The sequence of rows is a slower way of reading a column's values."""
    seer = User.objects.create_user(username="sam", password="secret")  # noqa: S106
    seer = grant(seer, Book, "view_book", "view_book_title")
    as_key(client, seer)
    body = client.get(f"{BASE}books/?order=-in_print").json()
    assert [r["title"] for r in body["results"]] == ["Book 0", "Book 1", "Book 2"]


def test_ordering_works_on_a_visible_column(client, reader, rows):
    as_key(client, reader)
    body = client.get(f"{BASE}books/?order=-title").json()
    assert [r["title"] for r in body["results"]] == ["Book 2", "Book 1", "Book 0"]


def test_the_page_size_is_capped(client, reader, rows):
    """Permissions decide what may be read; the cap decides how fast."""
    from plinta.contrib.api.query import MAX_PAGE_SIZE

    as_key(client, reader)
    assert client.get(f"{BASE}books/?size=99999").json()["size"] == MAX_PAGE_SIZE


def test_the_total_describes_the_filtered_set_not_the_page(client, reader, rows):
    as_key(client, reader)
    body = client.get(f"{BASE}books/?size=1").json()
    assert body["total"] == 3
    assert len(body["results"]) == 1
    assert body["pages"] == 3


def test_a_row_the_caller_may_not_see_is_404(client, db, books, rows):
    """Missing rather than forbidden: a pk is a number somebody can guess and
    a 403 would confirm the guess."""
    from plinta.permissions.policies import PermissionPolicy, register_policy
    from plinta.permissions.rules import Owner

    class Mine(PermissionPolicy):
        view = Owner("owner")

    register_policy(Book, Mine)
    eve = User.objects.create_user(username="eve", password="secret")  # noqa: S106
    eve = grant(eve, Book, "view_book", "view_book_title", "view_book_in_print")
    as_key(client, eve)
    assert client.get(f"{BASE}books/{rows.first().pk}/").status_code == 404


# --- writing ----------------------------------------------------------------


def test_a_write_goes_through_the_pipeline(client, reader, rows):
    """So an API edit is authorised, validated, audited and notified exactly
    like a UI edit."""
    reader = grant(reader, Book, "change_book", "change_book_title")
    as_key(client, reader)
    book = rows.first()
    response = client.patch(
        f"{BASE}books/{book.pk}/",
        data=json.dumps({"title": "Renamed"}),
        content_type="application/json",
    )
    book.refresh_from_db()
    assert response.status_code == 200
    assert book.title == "Renamed"


def test_a_field_the_caller_may_not_write_is_dropped(client, reader, rows):
    reader = grant(reader, Book, "change_book", "change_book_title")
    as_key(client, reader)
    book = rows.first()
    before = book.in_print
    client.patch(
        f"{BASE}books/{book.pk}/",
        data=json.dumps({"title": "Renamed", "in_print": not before}),
        content_type="application/json",
    )
    book.refresh_from_db()
    assert book.title == "Renamed"
    assert book.in_print == before


def test_a_write_without_permission_is_403(client, reader, rows):
    """The caller is known; it is what they asked for that is refused."""
    as_key(client, reader)
    response = client.patch(
        f"{BASE}books/{rows.first().pk}/",
        data=json.dumps({"title": "Renamed"}),
        content_type="application/json",
    )
    assert response.status_code == 403


def test_deleting_needs_the_delete_permission(client, reader, rows):
    as_key(client, reader)
    book = rows.first()
    assert client.delete(f"{BASE}books/{book.pk}/").status_code == 403

    grant(reader, Book, "delete_book")
    assert client.delete(f"{BASE}books/{book.pk}/").status_code == 204
    assert not Book.objects.filter(pk=book.pk).exists()


def test_a_write_emits_the_event_the_ui_emits(client, reader, rows, listen):
    """No second audit path: the pipeline is the only way in."""
    from plinta.events import signals

    seen = []
    listen(signals.object_written, lambda **kwargs: seen.append(kwargs.get("source")))
    reader = grant(reader, Book, "change_book", "change_book_title")
    as_key(client, reader)
    client.patch(
        f"{BASE}books/{rows.first().pk}/",
        data=json.dumps({"title": "Renamed"}),
        content_type="application/json",
    )
    assert "api" in seen

"""The write pipeline: what it refuses, in what order, and what it announces."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from plinta.blocks.write import WriteDenied, authorise, delete, write, write_or_errors
from plinta.events import signals
from plinta.permissions.fields import sync_model
from plinta.permissions.policies import PermissionPolicy, register_policy
from plinta.permissions.rules import Owner
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db

BOOK_FIELDS = {"title": True, "region": True, "in_print": True, "watchers": True}


def grant(user, *codenames):
    ct = ContentType.objects.get_for_model(Book)
    for codename in codenames:
        perm, _ = Permission.objects.get_or_create(
            codename=codename, content_type=ct, defaults={"name": codename}
        )
        user.user_permissions.add(perm)
    return User.objects.get(pk=user.pk)


@pytest.fixture
def writer(db):
    """A user who may add and change books, and every field of one."""
    sync_model(Book, BOOK_FIELDS)
    ada = User.objects.create(username="ada")
    return grant(
        ada,
        "add_book",
        "change_book",
        "delete_book",
        "view_book",
        "change_book_title",
        "change_book_region",
        "change_book_in_print",
    )


# --- authorising -----------------------------------------------------------


def test_a_user_without_the_model_permission_is_refused(db):
    sync_model(Book, BOOK_FIELDS)
    bob = User.objects.create(username="bob")
    with pytest.raises(WriteDenied, match="may not change"):
        authorise(bob, "change", Book(), ["title"])


def test_a_field_the_user_may_not_change_is_refused(writer):
    """Refused, not dropped: silently ignoring half a write would tell the
    caller it succeeded."""
    writer.user_permissions.remove(Permission.objects.get(codename="change_book_title"))
    ada = User.objects.get(pk=writer.pk)
    with pytest.raises(WriteDenied) as exc:
        authorise(ada, "change", Book(), ["title"])
    assert exc.value.denied_fields == ["title"]


def test_the_refusal_names_every_denied_field(writer):
    for codename in ("change_book_title", "change_book_in_print"):
        writer.user_permissions.remove(Permission.objects.get(codename=codename))
    ada = User.objects.get(pk=writer.pk)
    with pytest.raises(WriteDenied) as exc:
        authorise(ada, "change", Book(), ["title", "in_print", "region"])
    assert exc.value.denied_fields == ["in_print", "title"]


def test_writing_no_fields_needs_no_field_permission(writer):
    authorise(writer, "change", Book(), [])


def test_a_row_policy_refuses_someone_elses_row(writer, policy_registry):
    class BookPolicy(PermissionPolicy):
        change = Owner("owner")

    register_policy(Book, BookPolicy)
    bob = User.objects.create(username="bob")
    book = Book.objects.create(title="Dune", owner=bob)
    with pytest.raises(WriteDenied):
        authorise(writer, "change", book, ["title"])


def test_nothing_is_written_when_authorisation_fails(writer):
    """Permission gates before validation and before any mutation."""
    writer.user_permissions.remove(Permission.objects.get(codename="change_book_title"))
    ada = User.objects.get(pk=writer.pk)
    book = Book.objects.create(title="Dune", owner=ada)
    with pytest.raises(WriteDenied):
        write(book, {"title": "Changed"}, ada)
    assert Book.objects.get(pk=book.pk).title == "Dune"


# --- validating ------------------------------------------------------------


def test_validation_goes_through_the_model_layer(writer):
    """full_clean, so a model's own clean and its constraints are honoured."""
    with pytest.raises(ValidationError):
        write(Book(owner=writer), {"title": ""}, writer)


def test_a_rejected_write_saves_nothing(writer):
    with pytest.raises(ValidationError):
        write(Book(owner=writer), {"title": ""}, writer)
    assert not Book.objects.exists()


def test_write_or_errors_returns_them_instead(writer):
    saved, errors = write_or_errors(Book(owner=writer), {"title": ""}, writer)
    assert saved is None
    assert "title" in errors


def test_write_or_errors_still_raises_a_refusal(writer):
    """Refusing a write is not the same answer as failing to validate one."""
    writer.user_permissions.remove(Permission.objects.get(codename="change_book_title"))
    ada = User.objects.get(pk=writer.pk)
    with pytest.raises(WriteDenied):
        write_or_errors(Book(owner=ada), {"title": "Dune"}, ada)


# --- writing ---------------------------------------------------------------


def test_a_create_saves_the_row(writer):
    saved, _ = write(Book(owner=writer), {"title": "Dune"}, writer)
    assert saved.pk is not None
    assert Book.objects.get(pk=saved.pk).title == "Dune"


def test_an_update_saves_the_change(writer):
    book = Book.objects.create(title="Dune", owner=writer)
    write(book, {"title": "Emma"}, writer)
    assert Book.objects.get(pk=book.pk).title == "Emma"


def test_the_saved_row_is_always_returned(writer):
    """So an inline edit can refresh a column the database derived, without
    the caller asking for it."""
    book = Book.objects.create(title="Dune", owner=writer)
    saved, _ = write(book, {"title": "Emma"}, writer)
    assert saved.title == "Emma"


def test_a_many_to_many_is_applied_after_the_save(writer):
    """It needs a pk to point at."""
    bob = User.objects.create(username="bob")
    saved, _ = write(Book(owner=writer), {"title": "Dune", "watchers": [bob]}, writer)
    assert list(saved.watchers.all()) == [bob]


def test_a_relation_is_written(writer):
    north = Region.objects.create(name="North")
    saved, _ = write(Book(owner=writer), {"title": "Dune", "region": north}, writer)
    assert saved.region == north


# --- the diff --------------------------------------------------------------


def test_changes_report_before_and_after(writer):
    book = Book.objects.create(title="Dune", owner=writer)
    _, changes = write(book, {"title": "Emma"}, writer)
    assert changes == {"title": ("Dune", "Emma")}


def test_an_unchanged_field_is_not_reported(writer):
    book = Book.objects.create(title="Dune", owner=writer)
    _, changes = write(book, {"title": "Dune"}, writer)
    assert changes == {}


def test_a_create_reports_every_field_with_no_before(writer):
    _, changes = write(Book(owner=writer), {"title": "Dune"}, writer)
    assert changes == {"title": (None, "Dune")}


def test_a_many_to_many_appears_in_the_diff(writer):
    bob = User.objects.create(username="bob")
    book = Book.objects.create(title="Dune", owner=writer)
    _, changes = write(book, {"watchers": [bob]}, writer)
    assert changes == {"watchers": ([], [bob.pk])}


def test_the_before_comes_from_the_database(writer):
    """The in-memory instance already carries the new value by then."""
    book = Book.objects.create(title="Dune", owner=writer)
    book.title = "Changed in memory"
    _, changes = write(book, {"title": "Emma"}, writer)
    assert changes["title"][0] == "Dune"


# --- what it announces -----------------------------------------------------


def test_it_emits_writing_then_written(writer, listen):
    seen = []
    listen(signals.object_writing, lambda **kw: seen.append("writing"))
    listen(signals.object_written, lambda **kw: seen.append("written"))
    write(Book(owner=writer), {"title": "Dune"}, writer)
    assert seen == ["writing", "written"]


def test_writing_fires_before_the_row_exists(writer, listen):
    seen = {}

    def note(sender, obj, **kw):
        seen["saved"] = Book.objects.filter(title="Dune").exists()

    listen(signals.object_writing, note)
    write(Book(owner=writer), {"title": "Dune"}, writer)
    assert seen["saved"] is False


def test_written_carries_the_changes(writer, listen):
    seen = {}
    listen(signals.object_written, lambda sender, **kw: seen.update(kw))
    book = Book.objects.create(title="Dune", owner=writer)
    write(book, {"title": "Emma"}, writer)
    assert seen["mode"] == "update"
    assert seen["changes"] == {"title": ("Dune", "Emma")}


def test_the_actor_and_source_are_carried(writer, listen):
    seen = {}
    listen(signals.object_written, lambda sender, **kw: seen.update(kw))
    write(Book(owner=writer), {"title": "Dune"}, writer, source="import")
    assert seen["actor"] == writer
    assert seen["source"] == "import"


def test_a_refused_write_announces_nothing(writer, listen):
    seen = []
    writer.user_permissions.remove(Permission.objects.get(codename="change_book_title"))
    ada = User.objects.get(pk=writer.pk)
    listen(signals.object_writing, lambda **kw: seen.append(1))
    with pytest.raises(WriteDenied):
        write(Book(owner=ada), {"title": "Dune"}, ada)
    assert seen == []


def test_an_invalid_write_announces_nothing(writer, listen):
    seen = []
    listen(signals.object_writing, lambda **kw: seen.append(1))
    with pytest.raises(ValidationError):
        write(Book(owner=writer), {"title": ""}, writer)
    assert seen == []


# --- deleting --------------------------------------------------------------


def test_a_delete_removes_the_row(writer):
    book = Book.objects.create(title="Dune", owner=writer)
    delete(book, writer)
    assert not Book.objects.filter(pk=book.pk).exists()


def test_a_delete_is_refused_without_the_permission(writer):
    writer.user_permissions.remove(Permission.objects.get(codename="delete_book"))
    ada = User.objects.get(pk=writer.pk)
    book = Book.objects.create(title="Dune", owner=ada)
    with pytest.raises(WriteDenied):
        delete(book, ada)
    assert Book.objects.filter(pk=book.pk).exists()


def test_a_delete_announces_the_pk(writer, listen):
    """Django's collector clears it on the instance it deleted."""
    seen = {}
    book = Book.objects.create(title="Dune", owner=writer)
    pk = book.pk
    listen(signals.object_deleted, lambda sender, **kw: seen.update(kw))
    delete(book, writer)
    assert seen["pk"] == pk

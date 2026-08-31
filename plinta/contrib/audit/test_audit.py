"""An audit trail built by listening, and the proof that it is one."""
import pathlib

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.blocks.write import delete, write
from plinta.contrib.audit.listeners import describe, scrub
from plinta.contrib.audit.models import Action, AuditEntry
from plinta.events import signals
from plinta.permissions import allowed
from plinta.permissions.fields import sync_model
from tests.testapp.models import Book

pytestmark = pytest.mark.django_db

FIELDS = {"title": True, "in_print": True}


@pytest.fixture
def writer(db):
    sync_model(Book, FIELDS)
    ada = User.objects.create(username="ada")
    ct = ContentType.objects.get_for_model(Book)
    for codename in (
        "add_book", "change_book", "delete_book", "view_book",
        "change_book_title", "change_book_in_print",
    ):
        perm, _ = Permission.objects.get_or_create(
            codename=codename, content_type=ct, defaults={"name": codename}
        )
        ada.user_permissions.add(perm)
    return User.objects.get(pk=ada.pk)


# --- the point: core does not know this app exists -------------------------


def test_no_core_module_imports_it():
    """v1 called this from stages 12 to 14 of the write pipeline, which is why
    blocks imported it. Here the coupling runs the other way entirely.

    Asserted from the **imports**, not from the text. A core module may name
    the contrib namespace — `utils/checks.py` holds `"plinta.contrib."` to
    enforce the very rule this tests — and a string is not a dependency.
    """
    from tests.test_import_boundary import _imported_plinta_modules

    core = pathlib.Path(__file__).resolve().parents[2]
    importers = [
        path.relative_to(core.parent)
        for path in core.rglob("*.py")
        if "contrib" not in path.parts
        and "migrations" not in path.parts
        and any(
            m.startswith("plinta.contrib")
            for m in _imported_plinta_modules(path)
        )
    ]
    assert importers == []


def test_the_write_pipeline_has_no_audit_stage():
    """The specific thing that changed: three stages became no stages."""
    from plinta.blocks import write as pipeline

    source = pathlib.Path(pipeline.__file__).read_text(encoding="utf-8")
    assert "audit" not in source.lower()


def test_removing_the_app_removes_the_auditing(writer):
    """And leaves the write working, with no guard in core to take out — which
    is what "removable" has to mean to be worth claiming."""
    from plinta.contrib.audit import listeners

    listeners.disconnect()
    try:
        saved, _ = write(Book(owner=writer), {"title": "Dune"}, writer)
        assert saved.pk is not None
        assert not AuditEntry.objects.exists()
    finally:
        listeners.connect()


# --- what gets recorded ----------------------------------------------------


def test_a_create_is_recorded(writer):
    write(Book(owner=writer), {"title": "Dune"}, writer)
    entry = AuditEntry.objects.get()
    assert entry.action == Action.CREATED
    assert entry.target_label == "Book object (1)" or entry.target_label


def test_an_update_is_recorded_with_its_diff(writer):
    book = Book.objects.create(title="Dune", owner=writer)
    write(book, {"title": "Emma"}, writer)
    entry = AuditEntry.objects.get()
    assert entry.action == Action.UPDATED
    assert entry.changes == {"title": ["Dune", "Emma"]}


def test_a_delete_is_recorded(writer):
    book = Book.objects.create(title="Dune", owner=writer)
    pk = book.pk
    delete(book, writer)
    entry = AuditEntry.objects.get()
    assert entry.action == Action.DELETED
    assert entry.object_id == pk


def test_a_deleted_row_is_still_described(writer):
    """The relation dangles; the label is what survives, and a trail that
    cannot say what it was about is not one."""
    book = Book.objects.create(title="Dune", owner=writer)
    delete(book, writer)
    entry = AuditEntry.objects.get()
    assert entry.target is None
    assert entry.target_label


def test_the_actor_and_source_are_kept(writer):
    write(Book(owner=writer), {"title": "Dune"}, writer, source="import")
    entry = AuditEntry.objects.get()
    assert entry.actor == writer
    assert entry.source == "import"


def test_a_write_with_no_actor_is_still_recorded(writer):
    """An importer or a command has nobody signed in, and that is a fact worth
    recording rather than a reason to skip the row."""
    writer.is_superuser = True
    writer.save()
    signals.emit_written(
        Book.objects.create(title="Dune"), mode="create", changes={}, actor=None
    )
    assert AuditEntry.objects.get().actor is None


def test_a_state_change_is_recorded_as_a_diff(writer):
    """audit never imports workflow: the signal carries two names, and two
    names are a diff."""
    book = Book.objects.create(title="Dune", owner=writer)
    signals.emit_state_changed(book, from_state="draft", to_state="live", actor=writer)
    entry = AuditEntry.objects.get()
    assert entry.action == Action.STATE_CHANGED
    assert entry.changes == {"state": ["draft", "live"]}


def test_an_intention_is_not_recorded(writer):
    """object_writing fires before the write, and one that fails validation
    never happens — an audit trail of intentions records those too."""
    signals.emit_writing(Book(title="Dune"), mode="create", fields=["title"])
    assert not AuditEntry.objects.exists()


def test_an_unchanged_write_records_an_empty_diff(writer):
    book = Book.objects.create(title="Dune", owner=writer)
    write(book, {"title": "Dune"}, writer)
    assert AuditEntry.objects.get().changes == {}


# --- what is not recorded --------------------------------------------------


@pytest.mark.parametrize(
    "field", ["password", "PASSWORD", "api_key", "reset_token", "private_key_pem"]
)
def test_a_sensitive_field_is_redacted(field):
    assert scrub({field: ("old", "new")})[field] == ("[redacted]", "[redacted]")


def test_redaction_replaces_rather_than_drops():
    """Dropped, the entry would say nothing changed. Replaced, it says the
    field changed and declines to say to what."""
    scrubbed = scrub({"password": ("a", "b"), "title": ("x", "y")})
    assert set(scrubbed) == {"password", "title"}
    assert scrubbed["title"] == ("x", "y")


def test_disconnecting_needs_the_uid_it_was_connected_under(writer):
    """Django matches a uid-registered receiver by uid alone. Passing the
    function removes nothing and looks like it worked."""
    from plinta.contrib.audit import listeners

    signals.object_written.disconnect(listeners.on_written)
    write(Book(owner=writer), {"title": "Dune"}, writer)
    assert AuditEntry.objects.exists()


def test_an_ordinary_field_is_untouched():
    assert scrub({"title": ("a", "b")}) == {"title": ("a", "b")}


# --- robustness ------------------------------------------------------------


def test_a_model_whose_str_raises_is_still_recorded():
    class Awkward:
        pk = 1

        def __str__(self):
            raise ValueError("no")

    assert "unprintable" in describe(Awkward())


def test_a_long_label_is_truncated():
    class Verbose:
        def __str__(self):
            return "x" * 500

    assert len(describe(Verbose())) == 200


# --- reading it ------------------------------------------------------------


def test_the_trail_is_readable_by_a_holder(writer):
    write(Book(owner=writer), {"title": "Dune"}, writer)
    ct = ContentType.objects.get_for_model(AuditEntry)
    perm, _ = Permission.objects.get_or_create(
        codename="view_auditentry", content_type=ct, defaults={"name": "view audit"}
    )
    writer.user_permissions.add(perm)
    reader = User.objects.get(pk=writer.pk)
    assert allowed(reader, "view", AuditEntry.objects.all()).count() == 1


def test_without_the_permission_the_trail_is_invisible(writer):
    write(Book(owner=writer), {"title": "Dune"}, writer)
    assert allowed(writer, "view", AuditEntry.objects.all()).count() == 0


def test_it_is_not_narrowed_per_viewer(writer):
    """A trail filtered per reader cannot be reconciled. Who may read it is the
    model permission's question, not a row rule's."""
    from plinta.contrib.audit.policies import AuditEntryPolicy

    assert AuditEntryPolicy().rule_for("change") is None
    assert AuditEntryPolicy().rule_for("delete") is None


def test_which_fields_moved_is_readable(writer):
    book = Book.objects.create(title="Dune", owner=writer)
    write(book, {"title": "Emma", "in_print": False}, writer)
    assert AuditEntry.objects.get().fields_changed == ["in_print", "title"]


# --- what is recorded at all -----------------------------------------------


def test_a_consumers_model_is_recorded_without_opting_in(writer):
    """A trail you forgot to switch on is silent, and silence is the failure
    that matters here — so a consumer's model is in unless they say otherwise."""
    write(Book(owner=writer), {"title": "Dune"}, writer)
    assert AuditEntry.objects.count() == 1


def test_plintas_own_configuration_is_not_recorded(writer):
    """Somebody dragging a block would otherwise bury the writes the trail
    exists to show."""
    from plinta.blocks.models import Block
    from plinta.datasources.models import DataSource

    ds = DataSource.objects.create(
        name="books", label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    block = Block(name="t", component_type="table_plinta", data_source=ds)
    signals.emit_written(block, mode="create", changes={}, actor=writer)
    assert not AuditEntry.objects.exists()


def test_the_exclusions_are_a_setting(writer, settings):
    settings.PLINTA_AUDIT_EXCLUDE_APPS = ["testapp"]
    write(Book(owner=writer), {"title": "Dune"}, writer)
    assert not AuditEntry.objects.exists()


def test_an_empty_setting_records_everything(writer, settings):
    from plinta.contrib.audit.listeners import excluded_apps

    settings.PLINTA_AUDIT_EXCLUDE_APPS = []
    assert excluded_apps() == frozenset()


# --- failing without failing the write -------------------------------------


def test_a_broken_trail_does_not_fail_the_write(writer, monkeypatch, caplog):
    """Losing an audit row is bad; failing somebody's save because of one is
    worse."""

    def explode(*args, **kwargs):
        raise RuntimeError("audit database is down")

    monkeypatch.setattr(AuditEntry.objects, "create", explode)
    saved, _ = write(Book(owner=writer), {"title": "Dune"}, writer)
    assert saved.pk is not None
    assert "audit could not record" in caplog.text


# --- the screen ------------------------------------------------------------


def test_the_seeder_makes_a_page(writer):
    from django.core.management import call_command

    from plinta.pages.models import Page

    call_command("seed_audit_page", verbosity=0)
    assert Page.objects.filter(slug="audit-trail").exists()


def test_the_page_is_a_page_and_not_a_view(writer):
    """So it appears in the menu through the ordinary permission-filtered
    path, and disappears with the app rather than leaving a dead link."""
    from django.contrib.auth.models import Permission
    from django.core.management import call_command

    from plinta.pages.menu import build
    from plinta.pages.models import Page

    call_command("seed_audit_page", verbosity=0)
    perm, _ = Permission.objects.get_or_create(
        codename="view_page",
        content_type=ContentType.objects.get_for_model(Page),
        defaults={"name": "view page"},
    )
    writer.user_permissions.add(perm)
    reader = User.objects.get(pk=writer.pk)
    names = [p.name for section in build(reader) for p in section.pages]
    assert "Audit trail" in names


def test_the_seeder_is_idempotent(writer):
    from django.core.management import call_command

    from plinta.blocks.models import Block
    from plinta.pages.models import Page

    call_command("seed_audit_page", verbosity=0)
    counts = (Page.objects.count(), Block.objects.count())
    call_command("seed_audit_page", verbosity=0)
    assert (Page.objects.count(), Block.objects.count()) == counts


def test_the_page_reads_the_trail(writer):
    """Through the ordinary table component, over a DataSource like any other
    model — an audit log is rows, and plinta already draws rows."""
    from django.contrib.auth.models import Permission
    from django.core.management import call_command

    from plinta.blocks.models import Block
    from plinta.blocks.rendering import render_block
    from plinta.permissions.fields import sync_model

    write(Book(owner=writer), {"title": "Dune"}, writer)
    call_command("seed_audit_page", verbosity=0)

    sync_model(AuditEntry, {f.field_name: False for f in
                            Block.objects.get(name="audit-trail").data_source.fields.all()})
    ct = ContentType.objects.get_for_model(AuditEntry)
    for perm in Permission.objects.filter(content_type=ct):
        writer.user_permissions.add(perm)
    for model in (Block,):
        perm, _ = Permission.objects.get_or_create(
            codename="view_block",
            content_type=ContentType.objects.get_for_model(model),
            defaults={"name": "view block"},
        )
        writer.user_permissions.add(perm)
    reader = User.objects.get(pk=writer.pk)

    out = render_block(Block.objects.get(name="audit-trail"), reader)
    # "Created", not "created": a choices field renders its label.
    assert "Created" in out
    assert "Book object" in out

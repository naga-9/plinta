"""Notifications built by listening, and the four imports that no longer exist."""
import pathlib

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.management import call_command

from plinta.blocks.write import delete, write
from plinta.contrib.notifications import listeners
from plinta.contrib.notifications.models import (
    EmailStatus,
    Notification,
    NotificationPreference,
    QueuedEmail,
)
from plinta.contrib.notifications.registry import SubscriptionError, register_notification
from plinta.events import signals
from plinta.permissions import allowed
from plinta.permissions.fields import sync_model
from tests.testapp.models import Book

pytestmark = pytest.mark.django_db


@pytest.fixture
def subscriptions():
    """Empty subscription registry, restored afterwards."""
    from plinta.contrib.notifications import registry

    saved = dict(registry._registry)
    registry._registry.clear()
    yield registry
    registry._registry.clear()
    registry._registry.update(saved)


@pytest.fixture
def people(db):
    sync_model(Book, {"title": True})
    ada = User.objects.create(username="ada", email="ada@example.com")
    bob = User.objects.create(username="bob", email="bob@example.com")
    ct = ContentType.objects.get_for_model(Book)
    for codename in ("add_book", "change_book", "delete_book", "view_book",
                     "change_book_title"):
        perm, _ = Permission.objects.get_or_create(
            codename=codename, content_type=ct, defaults={"name": codename}
        )
        ada.user_permissions.add(perm)
    return User.objects.get(pk=ada.pk), bob


def watch(name="book_written", event="created", **kwargs):
    kwargs.setdefault("recipients", lambda obj, **kw: User.objects.all())
    return register_notification(name, "testapp.book", event, **kwargs)


# --- the point: nothing imports this app -----------------------------------


def test_no_core_module_imports_it():
    """Nothing in core knows this app exists; it subscribes to core's signals.

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


def test_the_write_pipeline_does_not_mention_notifications():
    from plinta.blocks import write as pipeline

    source = pathlib.Path(pipeline.__file__).read_text(encoding="utf-8")
    assert "notif" not in source.lower()


def test_two_listeners_do_not_know_about_each_other(people, subscriptions):
    """audit and notifications both hear the same write and neither imports
    the other — which is the property a shared bus buys."""
    from plinta.contrib.audit.models import AuditEntry

    ada, _ = people
    watch()
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert AuditEntry.objects.count() == 1
    assert Notification.objects.exists()


def test_removing_the_app_removes_the_notifying(people, subscriptions):
    ada, _ = people
    watch()
    listeners.disconnect()
    try:
        saved, _ = write(Book(owner=ada), {"title": "Dune"}, ada)
        assert saved.pk is not None
        assert not Notification.objects.exists()
    finally:
        listeners.connect()


# --- registering an interest -----------------------------------------------


def test_a_subscription_is_registered(subscriptions):
    assert watch().name == "book_written"


def test_a_duplicate_is_refused(subscriptions):
    watch()
    with pytest.raises(SubscriptionError, match="already registered"):
        watch()


@pytest.mark.parametrize("name", ["Book", "1st", "with-dash", ""])
def test_an_unusable_name_is_refused(subscriptions, name):
    with pytest.raises(SubscriptionError):
        watch(name=name)


def test_an_event_core_does_not_emit_is_refused(subscriptions):
    """A subscription naming one would simply never fire, which looks like a
    bug in whatever it was watching."""
    with pytest.raises(SubscriptionError, match="not an event plinta emits"):
        watch(event="exploded")


# --- who hears -------------------------------------------------------------


def test_the_recipients_are_told(people, subscriptions):
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob])
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert [n.recipient for n in Notification.objects.all()] == [bob]


def test_the_actor_is_not_told_by_default(people, subscriptions):
    """Telling somebody what they just did is the commonest complaint about a
    notification system."""
    ada, _ = people
    watch(recipients=lambda obj, **kw: User.objects.all())
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert ada not in [n.recipient for n in Notification.objects.all()]


def test_the_actor_may_be_told_when_asked(people, subscriptions):
    ada, _ = people
    watch(recipients=lambda obj, **kw: [ada], notify_actor=True)
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert Notification.objects.count() == 1


def test_a_recipient_listed_twice_is_told_once(people, subscriptions):
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob, bob])
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert Notification.objects.count() == 1


def test_a_condition_can_decline(people, subscriptions):
    ada, bob = people
    watch(
        recipients=lambda obj, **kw: [bob],
        when=lambda obj, **kw: obj.title == "Emma",
    )
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert not Notification.objects.exists()


def test_a_condition_sees_the_diff(people, subscriptions):
    ada, bob = people
    watch(
        event="updated",
        recipients=lambda obj, **kw: [bob],
        when=lambda obj, changes=None, **kw: "title" in (changes or {}),
    )
    book = Book.objects.create(title="Dune", owner=ada)
    write(book, {"title": "Emma"}, ada)
    assert Notification.objects.count() == 1


# --- which event -----------------------------------------------------------


def test_created_and_updated_are_separable(people, subscriptions):
    ada, bob = people
    watch(name="on_create", event="created", recipients=lambda obj, **kw: [bob])
    book = Book.objects.create(title="Dune", owner=ada)
    write(book, {"title": "Emma"}, ada)
    assert not Notification.objects.exists()


def test_written_covers_both(people, subscriptions):
    """So a subscription need not register twice to mean "whenever touched"."""
    ada, bob = people
    watch(name="either", event="written", recipients=lambda obj, **kw: [bob])
    write(Book(owner=ada), {"title": "Dune"}, ada)
    book = Book.objects.get()
    write(book, {"title": "Emma"}, ada)
    assert Notification.objects.count() == 2


def test_a_delete_is_an_event(people, subscriptions):
    ada, bob = people
    watch(event="deleted", recipients=lambda obj, **kw: [bob])
    book = Book.objects.create(title="Dune", owner=ada)
    delete(book, ada)
    assert Notification.objects.count() == 1


def test_a_state_change_needs_no_workflow_import(people, subscriptions):
    ada, bob = people
    watch(
        event="state_changed",
        recipients=lambda obj, **kw: [bob],
        title=lambda obj, to_state=None, **kw: f"Now {to_state}",
    )
    book = Book.objects.create(title="Dune", owner=ada)
    signals.emit_state_changed(book, from_state="draft", to_state="live", actor=ada)
    assert Notification.objects.get().title == "Now live"


def test_a_comment_needs_no_comments_import(people, subscriptions):
    """In v1 this was one of the four sideways imports."""
    ada, bob = people
    watch(
        event="comment_posted",
        recipients=lambda obj, **kw: [bob],
        title=lambda obj, body="", **kw: f"Comment: {body}",
    )
    book = Book.objects.create(title="Dune", owner=ada)
    signals.emit_comment_posted(book, body="nice one", actor=ada)
    assert Notification.objects.get().title == "Comment: nice one"


def test_a_subscription_ignores_other_models(people, subscriptions):
    ada, bob = people
    register_notification(
        "other", "auth.user", "created", recipients=lambda obj, **kw: [bob]
    )
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert not Notification.objects.exists()


# --- what it says ----------------------------------------------------------


def test_a_title_may_be_a_callable(people, subscriptions):
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob], title=lambda obj, **kw: f"New: {obj.title}")
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert Notification.objects.get().title == "New: Dune"


def test_a_title_may_be_a_plain_string(people, subscriptions):
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob], title="A book arrived")
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert Notification.objects.get().title == "A book arrived"


def test_without_a_title_the_object_names_itself(people, subscriptions):
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob])
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert Notification.objects.get().title


# --- preferences -----------------------------------------------------------


def test_the_registrations_defaults_apply_without_a_row(people, subscriptions):
    """A newly registered kind works before anybody has a preference for it."""
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob])
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert Notification.objects.exists()
    assert not QueuedEmail.objects.exists()


def test_a_preference_can_mute_one_channel(people, subscriptions):
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob])
    NotificationPreference.objects.create(
        user=bob, kind="book_written", channel="in_app", enabled=False
    )
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert not Notification.objects.exists()


def test_a_preference_is_per_channel(people, subscriptions):
    """So a person may take a kind by one route and not another."""
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob], title="A book arrived")
    NotificationPreference.objects.create(
        user=bob, kind="book_written", channel="email", enabled=True
    )
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert Notification.objects.count() == 1
    assert QueuedEmail.objects.get().to == "bob@example.com"


def test_a_subscription_may_default_a_channel_on(people, subscriptions):
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob], channels={"email": True})
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert QueuedEmail.objects.count() == 1


def test_somebody_who_cannot_be_reached_is_not(people, subscriptions):
    """No address, no email — however enthusiastically they opted in."""
    ada, bob = people
    bob.email = ""
    bob.save()
    watch(recipients=lambda obj, **kw: [bob], channels={"email": True})
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert not QueuedEmail.objects.exists()


# --- email is queued, never sent inline ------------------------------------


def test_a_write_sends_no_mail(people, subscriptions):
    """A mail server that is down must not be able to fail somebody's save."""
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob], channels={"email": True})
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert mail.outbox == []
    assert QueuedEmail.objects.get().status == EmailStatus.QUEUED


def test_the_command_sends_it(people, subscriptions):
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob], channels={"email": True}, title="Hello")
    write(Book(owner=ada), {"title": "Dune"}, ada)
    call_command("send_queued_email", verbosity=0)
    assert [m.subject for m in mail.outbox] == ["Hello"]
    assert QueuedEmail.objects.get().status == EmailStatus.SENT


def test_a_sent_message_is_not_sent_twice(people, subscriptions):
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob], channels={"email": True})
    write(Book(owner=ada), {"title": "Dune"}, ada)
    call_command("send_queued_email", verbosity=0)
    call_command("send_queued_email", verbosity=0)
    assert len(mail.outbox) == 1


def test_a_failure_is_recorded_and_retried_a_bounded_number_of_times(
    people, subscriptions, monkeypatch
):
    """A queue that retries for ever is a queue that never drains."""
    from plinta.contrib.notifications.management.commands import send_queued_email

    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob], channels={"email": True})
    write(Book(owner=ada), {"title": "Dune"}, ada)

    def explode(*args, **kwargs):
        raise RuntimeError("no mail server")

    monkeypatch.setattr(send_queued_email, "send_mail", explode)
    for _ in range(send_queued_email.MAX_ATTEMPTS + 2):
        call_command("send_queued_email", "--retry-failed", verbosity=0)

    message = QueuedEmail.objects.get()
    assert message.status == EmailStatus.FAILED
    assert message.attempts == send_queued_email.MAX_ATTEMPTS
    assert "no mail server" in message.last_error


# --- failing without failing the write -------------------------------------


def test_a_broken_recipient_callable_does_not_fail_the_write(people, subscriptions, caplog):
    ada, _ = people

    def explode(obj, **kw):
        raise RuntimeError("who?")

    watch(recipients=explode)
    saved, _ = write(Book(owner=ada), {"title": "Dune"}, ada)
    assert saved.pk is not None
    assert "recipients for" in caplog.text


def test_a_broken_condition_declines_rather_than_raises(people, subscriptions, caplog):
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob], when=lambda obj, **kw: 1 / 0)
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert not Notification.objects.exists()
    assert "condition for" in caplog.text


# --- reading them ----------------------------------------------------------


def test_a_notification_is_the_recipients_alone(people, subscriptions):
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob])
    write(Book(owner=ada), {"title": "Dune"}, ada)

    ct = ContentType.objects.get_for_model(Notification)
    perm, _ = Permission.objects.get_or_create(
        codename="view_notification", content_type=ct, defaults={"name": "view"}
    )
    for person in (ada, bob):
        person.user_permissions.add(perm)

    assert allowed(User.objects.get(pk=bob.pk), "view", Notification.objects.all()).count() == 1
    assert allowed(User.objects.get(pk=ada.pk), "view", Notification.objects.all()).count() == 0


def test_marking_read_is_idempotent(people, subscriptions):
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob])
    write(Book(owner=ada), {"title": "Dune"}, ada)
    note = Notification.objects.get()
    note.mark_read()
    first = note.read_at
    note.mark_read()
    assert note.read_at == first
    assert note.is_read


# --- a third channel, from outside -----------------------------------------


@pytest.fixture
def channel_registry():
    """Channels as installed, restored afterwards."""
    from plinta.contrib.notifications import channels

    saved = dict(channels._registry)
    yield channels
    channels._registry.clear()
    channels._registry.update(saved)


def test_a_third_party_may_add_a_channel(people, subscriptions, channel_registry):
    """Discord, Slack, SMS, a webhook — a package that registers one, not a
    change to this app."""
    sent = []
    channel_registry.register_channel(
        "discord",
        "Discord",
        deliver=lambda user, notification, **kw: sent.append(
            (user.username, notification.title)
        ),
        on_by_default=True,
    )
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob], title="A book arrived")
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert sent == [("bob", "A book arrived")]


def test_a_new_channel_does_not_switch_itself_on(people, subscriptions, channel_registry):
    """Installing a package must not start messaging everybody."""
    sent = []
    channel_registry.register_channel(
        "discord", deliver=lambda user, notification, **kw: sent.append(1)
    )
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob])
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert sent == []


def test_a_channel_declares_who_it_can_reach(people, subscriptions, channel_registry):
    sent = []
    channel_registry.register_channel(
        "discord",
        deliver=lambda user, notification, **kw: sent.append(user.username),
        available=lambda user, **kw: user.username == "bob",
        on_by_default=True,
    )
    ada, bob = people
    watch(recipients=lambda obj, **kw: User.objects.all(), notify_actor=True)
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert sent == ["bob"]


def test_a_channel_appears_in_the_preferences(channel_registry):
    """Which is what a preference screen lists — it asks the registry rather
    than knowing the two that shipped."""
    channel_registry.register_channel("discord", deliver=lambda **kw: None)
    assert [c.name for c in channel_registry.registered()] == [
        "discord", "email", "in_app",
    ]


def test_a_broken_channel_does_not_stop_the_others(
    people, subscriptions, channel_registry, caplog
):
    channel_registry.register_channel(
        "discord",
        deliver=lambda user, notification, **kw: 1 / 0,
        on_by_default=True,
    )
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob])
    saved, _ = write(Book(owner=ada), {"title": "Dune"}, ada)
    assert saved.pk is not None
    assert Notification.objects.count() == 1
    assert "could not deliver" in caplog.text


def test_a_duplicate_channel_is_refused(channel_registry):
    from plinta.contrib.notifications.channels import ChannelError

    with pytest.raises(ChannelError, match="already registered"):
        channel_registry.register_channel("email", deliver=lambda **kw: None)


def test_a_preference_overrides_a_channel_default(
    people, subscriptions, channel_registry
):
    sent = []
    channel_registry.register_channel(
        "discord",
        deliver=lambda user, notification, **kw: sent.append(1),
        on_by_default=True,
    )
    ada, bob = people
    watch(recipients=lambda obj, **kw: [bob])
    NotificationPreference.objects.create(
        user=bob, kind="book_written", channel="discord", enabled=False
    )
    write(Book(owner=ada), {"title": "Dune"}, ada)
    assert sent == []

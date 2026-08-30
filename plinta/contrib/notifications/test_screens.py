"""The bell, the list and the preference grid — reached through the real client."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.contrib.notifications.models import Notification, NotificationPreference
from plinta.contrib.notifications.registry import register_notification
from plinta.shell.topbar import registered as topbar_items
from plinta.shell.topbar import visible_items

pytestmark = pytest.mark.django_db


@pytest.fixture
def subscriptions():
    from plinta.contrib.notifications import registry

    saved = dict(registry._registry)
    registry._registry.clear()
    yield registry
    registry._registry.clear()
    registry._registry.update(saved)


@pytest.fixture
def reader(db, client):
    ada = User.objects.create_user(username="ada", password="x", email="a@b.co")  # noqa: S106
    ct = ContentType.objects.get_for_model(Notification)
    perm, _ = Permission.objects.get_or_create(
        codename="view_notification", content_type=ct, defaults={"name": "view"}
    )
    ada.user_permissions.add(perm)
    ada = User.objects.get(pk=ada.pk)
    client.force_login(ada)
    return ada


def note(user, title="Something happened", **kwargs):
    return Notification.objects.create(
        recipient=user, kind="book_written", title=title, **kwargs
    )


# --- the bell is contributed, not built in ---------------------------------


def test_the_bell_is_registered_by_this_app():
    """Core draws whatever is registered and names no package — a bell in the
    base template would be core knowing about notifications."""
    assert "notifications" in [item.name for item in topbar_items()]


def test_the_bell_needs_the_permission(db):
    stranger = User.objects.create(username="nobody")
    assert visible_items(stranger) == []


def test_the_bell_appears_in_the_topbar(reader, client):
    body = client.get("/notifications/").content.decode()
    assert "aria-label=\"Notifications" in body


def test_it_counts_only_what_is_unread(reader, client):
    note(reader, "one")
    note(reader, "two", read_at="2026-01-01T00:00:00Z")
    body = client.get("/notifications/").content.decode()
    assert "1 unread" in body


def test_a_zero_badge_is_not_drawn(reader, client):
    """Nothing to say is better said by saying nothing."""
    body = client.get("/notifications/").content.decode()
    assert "pl-chip" not in body.split("</header>")[0]


# --- the list --------------------------------------------------------------


def test_the_list_shows_this_viewers_own(reader, client):
    note(reader, "for me")
    assert "for me" in client.get("/notifications/").content.decode()


def test_it_shows_nobody_elses(reader, client):
    other = User.objects.create(username="bob")
    note(other, "for bob")
    assert "for bob" not in client.get("/notifications/").content.decode()


def test_an_empty_list_says_so(reader, client):
    assert "Nothing yet" in client.get("/notifications/").content.decode()


def test_marking_one_read(reader, client):
    notification = note(reader)
    client.get(f"/notifications/{notification.pk}/read/")
    notification.refresh_from_db()
    assert notification.is_read


def test_somebody_elses_is_not_found(reader, client):
    """Not refused — the id is guessable, and a refusal confirms it exists."""
    other = User.objects.create(username="bob")
    notification = note(other)
    assert client.get(f"/notifications/{notification.pk}/read/").status_code == 404


def test_marking_all_read(reader, client):
    note(reader, "one")
    note(reader, "two")
    client.get("/notifications/read-all/")
    assert not Notification.objects.filter(read_at__isnull=True).exists()


def test_an_anonymous_visitor_is_sent_to_login(client):
    response = client.get("/notifications/")
    assert response.status_code == 302


# --- the preference grid ---------------------------------------------------


def test_both_axes_come_from_their_registries(reader, client, subscriptions):
    """A package adding a channel adds a column and one adding a subscription
    adds a row, neither touching the view."""
    register_notification(
        "sale_recorded", "contribapp.article", "created",
        recipients=lambda obj, **kw: [],
    )
    response = client.get("/notifications/preferences/")
    body = response.content.decode()
    assert "sale_recorded" in body
    assert "In The App" in body or "In the app" in body


def test_a_channel_the_viewer_cannot_use_is_not_offered(reader, client, subscriptions):
    """No address, no email column — an unusable checkbox is a lie."""
    register_notification(
        "sale_recorded", "contribapp.article", "created",
        recipients=lambda obj, **kw: [],
    )
    reader.email = ""
    reader.save()
    body = client.get("/notifications/preferences/").content.decode()
    assert "Email" not in body


def test_saving_writes_a_preference(reader, client, subscriptions):
    register_notification(
        "sale_recorded", "contribapp.article", "created",
        recipients=lambda obj, **kw: [],
    )
    client.post("/notifications/preferences/", {"sale_recorded:email": "on"})
    assert NotificationPreference.objects.get(
        user=reader, kind="sale_recorded", channel="email"
    ).enabled


def test_an_unticked_box_is_a_stored_no(reader, client, subscriptions):
    """Rather than an absent row, which would let the default drift back."""
    register_notification(
        "sale_recorded", "contribapp.article", "created",
        recipients=lambda obj, **kw: [],
    )
    client.post("/notifications/preferences/", {})
    assert not NotificationPreference.objects.get(
        user=reader, kind="sale_recorded", channel="in_app"
    ).enabled


def test_with_nothing_subscribed_the_grid_says_so(reader, client, subscriptions):
    assert "Nothing subscribes" in client.get(
        "/notifications/preferences/"
    ).content.decode()

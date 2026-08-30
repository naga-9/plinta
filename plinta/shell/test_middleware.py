"""The gate: who is redirected, and what is let through."""
import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.test import override_settings

from plinta.shell.checks import check_login_required_middleware
from plinta.shell.middleware import LoginRequiredMiddleware

MIDDLEWARE = "plinta.shell.middleware.LoginRequiredMiddleware"
AUTH = "django.contrib.auth.middleware.AuthenticationMiddleware"


class Request:
    def __init__(self, path="/pages/1-catalog/", user=None):
        self.path = path
        self.user = user

    def get_full_path(self):
        return self.path


def gate(response="ok"):
    return LoginRequiredMiddleware(lambda request: response)


# --- who is redirected -----------------------------------------------------


def test_an_anonymous_request_is_redirected():
    assert gate()(Request(user=AnonymousUser())).status_code == 302


def test_the_redirect_carries_where_they_were_going():
    """So logging in lands them on the page they asked for."""
    response = gate()(Request(path="/pages/7-books/", user=AnonymousUser()))
    assert "/pages/7-books/" in response.url


@pytest.mark.django_db
def test_an_authenticated_request_passes():
    user = User.objects.create(username="ada")
    assert gate()(Request(user=user)) == "ok"


def test_a_request_with_no_user_passes():
    """Nothing to gate. AuthenticationMiddleware puts it there, and the boot
    check reports its absence."""
    assert gate()(Request(user=None)) == "ok"


# --- what is exempt --------------------------------------------------------


@pytest.mark.parametrize(
    "path", ["/accounts/login/", "/static/plinta/css/plinta.css", "/api/v1/data/books/"]
)
def test_the_default_exemptions(path):
    assert gate()(Request(path=path, user=AnonymousUser())) == "ok"


@override_settings(PLINTA_LOGIN_EXEMPT_PREFIXES=["/health/"])
def test_a_declared_prefix_is_exempt():
    assert gate()(Request(path="/health/", user=AnonymousUser())) == "ok"


@override_settings(MEDIA_URL="/")
def test_an_everything_prefix_is_dropped():
    """Django's default MEDIA_URL is "/", and honouring it would exempt the
    whole site while looking like it was configured."""
    assert gate()(Request(user=AnonymousUser())).status_code == 302


@override_settings(PLINTA_API_PREFIX="/rest/")
def test_the_api_mount_follows_its_setting():
    """The same value mounts the API, so the two cannot drift and an XHR
    caller keeps getting JSON rather than an HTML redirect."""
    middleware = gate()
    assert middleware.is_exempt("/rest/v1/data/books/")
    assert not middleware.is_exempt("/api/v1/data/books/")


def test_a_path_merely_containing_an_exempt_prefix_is_not_exempt():
    assert gate()(Request(path="/pages/static/", user=AnonymousUser())).status_code == 302


def test_the_prefixes_are_resolved_once():
    middleware = gate()
    assert middleware.exempt_prefixes() is middleware.exempt_prefixes()


# --- the boot check --------------------------------------------------------


@override_settings(MIDDLEWARE=[AUTH, MIDDLEWARE])
def test_installed_after_authentication_is_quiet():
    assert check_login_required_middleware() == []


@override_settings(MIDDLEWARE=[AUTH])
def test_absent_is_an_error():
    """Every page below would decide permissions for an anonymous user."""
    errors = check_login_required_middleware()
    assert [e.id for e in errors] == ["plinta.shell.E001"]


@override_settings(MIDDLEWARE=[MIDDLEWARE, AUTH])
def test_installed_too_early_is_an_error():
    """request.user does not exist yet, so nothing is gated — and it looks
    like it is working, which is why this is checked rather than documented."""
    errors = check_login_required_middleware()
    assert [e.id for e in errors] == ["plinta.shell.E002"]


@override_settings(MIDDLEWARE=[MIDDLEWARE])
def test_without_authentication_middleware_the_order_is_not_judged():
    """A consumer may put the user there another way; the absent check above
    is not this check's business."""
    assert check_login_required_middleware() == []


@override_settings(MIDDLEWARE=[AUTH])
def test_the_hint_names_what_to_add():
    assert MIDDLEWARE in check_login_required_middleware()[0].hint

"""The five template helpers, and the shell's two context processors."""
import datetime

import pytest
from django.contrib.auth.models import AnonymousUser, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings

from plinta.pages.models import MenuGroup, MenuSection, Page
from plinta.shell.context_processors import branding, menu
from plinta.shell.templatetags.plinta_tags import (
    classify_value,
    get_item,
    isodate,
    site_name,
    to_json,
)


class Request:
    def __init__(self, user=None):
        self.user = user


# --- site_name -------------------------------------------------------------


def test_site_name_defaults():
    assert site_name() == "plinta"


@override_settings(PLINTA_SITE_NAME="Acme")
def test_site_name_follows_the_setting():
    assert site_name() == "Acme"


# --- get_item --------------------------------------------------------------


def test_get_item_reads_a_dict():
    assert get_item({"a": 1}, "a") == 1


def test_get_item_reads_an_attribute():
    assert get_item(datetime.date(2026, 1, 9), "year") == 2026


def test_a_missing_key_is_none_not_an_error():
    """A template cannot catch, so a missing column must draw as empty."""
    assert get_item({"a": 1}, "b") is None
    assert get_item(None, "a") is None


# --- classify_value --------------------------------------------------------


@pytest.mark.parametrize(
    "value,kind",
    [
        (None, "empty"),
        ("", "empty"),
        (True, "boolean"),
        (False, "boolean"),
        ({"a": 1}, "mapping"),
        ([1, 2], "sequence"),
        ((1, 2), "sequence"),
        (5, "number"),
        (5.5, "number"),
        ("text", "text"),
    ],
)
def test_classify_value(value, kind):
    assert classify_value(value) == kind


def test_a_boolean_is_not_a_number():
    """bool subclasses int, so the order of the checks decides."""
    assert classify_value(True) == "boolean"


def test_zero_is_a_number_not_empty():
    """A count of zero is a value; only None and the empty string are empty."""
    assert classify_value(0) == "number"


# --- isodate ---------------------------------------------------------------


def test_isodate_reformats():
    assert isodate("2026-01-09") == "09-01-2026"


def test_isodate_takes_a_format():
    assert isodate("2026-01-09", "%d %b %Y") == "09 Jan 2026"


def test_isodate_handles_a_timestamp():
    assert isodate("2026-01-09T14:30:00Z") == "09-01-2026"


def test_something_unparseable_is_left_alone():
    """Better a raw value on the page than an exception in a template."""
    assert isodate("not a date") == "not a date"


def test_nothing_is_empty():
    assert isodate(None) == ""
    assert isodate("") == ""


# --- to_json ---------------------------------------------------------------


def test_to_json_serialises():
    assert to_json({"a": 1}) == '{"a": 1}'


def test_none_is_empty():
    assert to_json(None) == ""


def test_a_closing_tag_cannot_escape_the_script():
    """A string containing </script> would otherwise close the tag it sits in."""
    out = to_json({"x": "</script><script>alert(1)</script>"})
    assert "</script>" not in out
    assert "<" not in out and ">" not in out


def test_an_ampersand_is_escaped_too():
    """It could start an HTML entity in an attribute value."""
    assert "&" not in to_json({"q": "a & b"})


# --- branding --------------------------------------------------------------


def test_branding_has_defaults():
    assert branding(Request()) == {"site_name": "plinta", "topbar_color": ""}


@override_settings(PLINTA_SITE_NAME="Acme", TOPBAR_COLOR="#663399")
def test_branding_follows_the_settings():
    assert branding(Request())["topbar_color"] == "#663399"


# --- menu ------------------------------------------------------------------


@pytest.mark.django_db
def test_the_menu_is_the_viewers():
    ada = User.objects.create(username="ada")
    perm, _ = Permission.objects.get_or_create(
        codename="view_page",
        content_type=ContentType.objects.get_for_model(Page),
        defaults={"name": "view page"},
    )
    ada.user_permissions.add(perm)
    ada = User.objects.get(pk=ada.pk)

    section = MenuSection.objects.create(name="Reference")
    group = MenuGroup.objects.create(section=section, name="Catalog")
    Page.objects.create(name="Books", slug="books", owner=ada, menu_group=group)

    sections = menu(Request(ada))["menu_sections"]
    assert [s.section.name for s in sections] == ["Reference"]


@pytest.mark.django_db
def test_an_anonymous_viewer_gets_no_menu():
    """It is built per request, so this saves the queries rather than the
    permission check — which would have refused it anyway."""
    assert menu(Request(AnonymousUser()))["menu_sections"] == []


def test_no_user_at_all_gets_no_menu():
    assert menu(Request())["menu_sections"] == []

"""Stored filter values naming a token nothing provides."""
import pytest
from django.contrib.auth.models import User

from plinta.pages.checks import check_filter_placeholders
from plinta.pages.models import FilterSet, Page, PageFilter, PageFilterPreference

pytestmark = pytest.mark.django_db


@pytest.fixture
def page(db):
    return Page.objects.create(name="Catalog", slug="catalog")


def test_nothing_stored_is_quiet(page, placeholder_registry):
    assert check_filter_placeholders() == []


def test_a_value_without_tokens_is_quiet(page, placeholder_registry):
    FilterSet.objects.create(page=page, name="mine", values={"region": "North"})
    assert check_filter_placeholders() == []


def test_a_registered_token_is_quiet(page, placeholder_registry):
    placeholder_registry.register_placeholder("me", lambda ctx: ctx.user.pk)
    FilterSet.objects.create(page=page, name="mine", values={"owner": "__ME__"})
    assert check_filter_placeholders() == []


def test_an_unregistered_token_in_a_filter_set_is_an_error(page, placeholder_registry):
    FilterSet.objects.create(page=page, name="mine", values={"owner": "__ME__"})
    errors = check_filter_placeholders()
    assert [e.id for e in errors] == ["plinta.pages.E001"]
    assert "filter set mine" in errors[0].msg


def test_a_controls_default_is_checked(page, placeholder_registry):
    PageFilter.objects.create(
        page=page, field_name="owner", label="Owner", default_value="__ME__"
    )
    assert "filter Owner" in check_filter_placeholders()[0].msg


def test_remembered_state_is_checked(page, placeholder_registry):
    ada = User.objects.create(username="ada")
    PageFilterPreference.objects.create(
        page=page, owner=ada, values={"owner": "__ME__"}
    )
    assert "remembered filters" in check_filter_placeholders()[0].msg


def test_a_control_with_no_default_is_skipped(page, placeholder_registry):
    PageFilter.objects.create(page=page, field_name="owner", label="Owner")
    assert check_filter_placeholders() == []


def test_the_hint_lists_what_is_registered(page, placeholder_registry):
    placeholder_registry.register_placeholder("today", lambda ctx: None)
    FilterSet.objects.create(page=page, name="mine", values={"owner": "__ME__"})
    assert "today" in check_filter_placeholders()[0].hint


def test_every_offender_is_reported(page, placeholder_registry):
    FilterSet.objects.create(page=page, name="one", values={"owner": "__ME__"})
    FilterSet.objects.create(page=page, name="two", values={"due": "__QUARTER__"})
    assert len(check_filter_placeholders()) == 2

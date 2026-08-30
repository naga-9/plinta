"""A block whose locked filter names a token nothing provides."""
import pytest
from django.contrib.contenttypes.models import ContentType

from plinta.blocks.checks import check_base_filter_placeholders
from plinta.blocks.models import Block
from plinta.datasources.models import DataSource
from tests.testapp.models import Book

pytestmark = pytest.mark.django_db


@pytest.fixture
def ds(db):
    return DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )


def block(ds, base_filter):
    return Block.objects.create(
        name="books-table",
        component_type="table_plinta",
        data_source=ds,
        base_filter=base_filter,
    )


def test_no_filter_is_quiet(ds, placeholder_registry):
    block(ds, {})
    assert check_base_filter_placeholders() == []


def test_a_filter_without_tokens_is_quiet(ds, placeholder_registry):
    block(ds, {"in_print": True})
    assert check_base_filter_placeholders() == []


def test_a_registered_token_is_quiet(ds, placeholder_registry):
    placeholder_registry.register_placeholder("me", lambda ctx: ctx.user.pk)
    block(ds, {"owner": "__ME__"})
    assert check_base_filter_placeholders() == []


def test_an_unregistered_token_is_an_error(ds, placeholder_registry):
    block(ds, {"owner": "__ME__"})
    errors = check_base_filter_placeholders()
    assert [e.id for e in errors] == ["plinta.blocks.E001"]
    assert "me" in errors[0].msg


def test_the_error_names_the_block(ds, placeholder_registry):
    block(ds, {"owner": "__ME__"})
    assert "books-table" in check_base_filter_placeholders()[0].msg


def test_the_hint_lists_what_is_registered(ds, placeholder_registry):
    placeholder_registry.register_placeholder("today", lambda ctx: None)
    block(ds, {"owner": "__ME__"})
    assert "today" in check_base_filter_placeholders()[0].hint


def test_a_token_inside_a_list_is_caught(ds, placeholder_registry):
    block(ds, {"owner__in": ["__ME__"]})
    assert check_base_filter_placeholders() != []


def test_it_catches_a_token_whose_provider_was_removed(ds, placeholder_registry):
    """The realistic failure: the block outlives the code behind the token."""
    placeholder_registry.register_placeholder("me", lambda ctx: ctx.user.pk)
    block(ds, {"owner": "__ME__"})
    assert check_base_filter_placeholders() == []
    placeholder_registry._registry.clear()
    assert check_base_filter_placeholders() != []

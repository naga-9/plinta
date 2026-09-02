"""Saving a page's filters.

The same species as a saved view, with one deliberate difference: a view
stores a **delta** over its block, a filter set stores its values **whole**.
A view's settings are presentation, where inheriting a later change is usually
wanted. Filter values are answers, and an absent one means *no filter* — a
real answer, not a missing one.
"""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.blocks.write import WriteDenied
from plinta.pages.filter_sets import (
    kept,
    may_default,
    may_publish,
    save,
    visible_sets,
)
from plinta.pages.models import FilterSet, Page, PageFilter

pytestmark = pytest.mark.django_db


def grant(user, model, *codenames):
    content_type = ContentType.objects.get_for_model(model)
    for codename in codenames:
        user.user_permissions.add(
            Permission.objects.get_or_create(
                codename=codename, content_type=content_type,
                defaults={"name": codename},
            )[0]
        )
    return User.objects.get(pk=user.pk)


@pytest.fixture
def page(db):
    owner = User.objects.create_user(username="ada", password="x")  # noqa: S106
    page = Page.objects.create(name="Catalogue", slug="catalogue", owner=owner)
    PageFilter.objects.create(page=page, field_name="region", label="Region")
    PageFilter.objects.create(page=page, field_name="in_print", label="In print")
    return page


@pytest.fixture
def ada(page):
    """Somebody who may save a set, and may neither publish nor default one."""
    return grant(
        User.objects.get(username="ada"),
        FilterSet,
        "add_filterset",
        "change_filterset",
        "view_filterset",
        "change_filterset_name",
        "change_filterset_values",
    )


# --- what a set holds -------------------------------------------------------


def test_the_values_are_stored_whole(page, ada):
    """Not a delta. An absent filter means no filter, which is an answer."""
    saved = save(page, ada, name="North", values={"region": "North"})
    assert saved.values == {"region": "North"}


def test_a_filter_the_page_does_not_declare_is_dropped(page, ada):
    """The bar is what the page offers; a query string is not."""
    saved = save(page, ada, name="Odd", values={"region": "North", "salary": "1"})
    assert saved.values == {"region": "North"}


def test_a_blank_is_not_a_filter(page, ada):
    saved = save(page, ada, name="Empty", values={"region": "", "in_print": "True"})
    assert saved.values == {"in_print": "True"}


def test_kept_narrows_without_saving(page):
    assert kept(page, {"region": "N", "nope": "x", "in_print": None}) == {"region": "N"}


# --- who may do what --------------------------------------------------------


def test_a_set_is_personal_by_default(page, ada):
    assert save(page, ada, name="Mine", values={}).owner == ada


def test_publishing_needs_the_field_permission(page, ada):
    """A change to `owner`, gated by the permission on that field."""
    with pytest.raises(WriteDenied, match="owner"):
        save(page, ada, name="Everyone's", values={}, public=True)


def test_publishing_with_it_makes_it_public(page, ada):
    granted = grant(ada, FilterSet, "change_filterset_owner")
    assert may_publish(granted)
    assert save(page, granted, name="All", values={}, public=True).owner is None


def test_defaulting_needs_its_own_permission(page, ada):
    assert not may_default(ada)
    with pytest.raises(WriteDenied, match="is_default"):
        save(page, ada, name="Start", values={}, default=True)


def test_saving_at_all_needs_the_model_permission(page):
    stranger = User.objects.create_user(username="eve", password="x")  # noqa: S106
    with pytest.raises(WriteDenied):
        save(page, stranger, name="Theirs", values={})


def test_an_existing_set_is_updated_not_duplicated(page, ada):
    first = save(page, ada, name="Mine", values={"region": "North"})
    again = save(page, ada, name="Renamed", values={"region": "South"},
                 filter_set=first)
    assert again.pk == first.pk
    assert again.values == {"region": "South"}
    assert FilterSet.objects.count() == 1


# --- one default per owner --------------------------------------------------


def test_marking_a_default_clears_the_previous_one(page, ada):
    """`default_filters` takes the first it finds, so two would mean
    whichever the query returned."""
    granted = grant(ada, FilterSet, "change_filterset_is_default")
    first = save(page, granted, name="One", values={}, default=True)
    save(page, granted, name="Two", values={}, default=True)
    first.refresh_from_db()
    assert first.is_default is False


def test_a_public_default_and_a_private_one_coexist(page, ada):
    granted = grant(ada, FilterSet, "change_filterset_is_default",
                    "change_filterset_owner")
    shared = save(page, granted, name="All", values={}, public=True, default=True)
    mine = save(page, granted, name="Mine", values={}, default=True)
    shared.refresh_from_db()
    mine.refresh_from_db()
    assert shared.is_default and mine.is_default


# --- what a viewer sees -----------------------------------------------------


def test_only_the_sets_this_viewer_may_see(page, ada):
    other = User.objects.create_user(username="bob", password="x")  # noqa: S106
    save(page, ada, name="Mine", values={})
    FilterSet.objects.create(page=page, name="Theirs", owner=other, values={})
    assert [s.name for s in visible_sets(page, ada)] == ["Mine"]

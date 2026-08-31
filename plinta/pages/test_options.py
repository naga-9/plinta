"""What a filter offers to choose from — and what it must not."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.datasources.models import DataSource
from plinta.pages.models import Page, PageFilter, Widget
from plinta.pages.options import options_for
from plinta.permissions.policies import PermissionPolicy, register_policy
from plinta.permissions.rules import FieldInUserSet
from tests.testapp.models import Book, Region


@pytest.fixture
def screen(db):
    north = Region.objects.create(name="North")
    south = Region.objects.create(name="South")
    ada = User.objects.create(username="ada")
    source = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    page = Page.objects.create(name="Catalogue", slug="catalogue")
    control = PageFilter.objects.create(
        page=page,
        field_name="region",
        label="Region",
        widget=Widget.SELECT,
        data_source=source,
    )
    return control, ada, north, south


def grant(user, model, codename):
    ct = ContentType.objects.get_for_model(model)
    perm, _ = Permission.objects.get_or_create(
        codename=codename, content_type=ct, defaults={"name": codename}
    )
    user.user_permissions.add(perm)
    return User.objects.get(pk=user.pk)


def test_a_relation_offers_its_rows(screen):
    control, ada, north, south = screen
    ada = grant(ada, Region, "view_region")
    labels = [label for _, label in options_for(control, ada)]
    assert sorted(labels) == ["North", "South"]


def test_a_viewer_without_the_model_permission_is_offered_nothing(screen):
    """Tier one applies to the option list as much as to the rows. Offering
    them would name rows the viewer may not see."""
    control, ada, _, _ = screen
    assert options_for(control, ada) == []


def test_the_policy_narrows_the_list(screen, policy_registry):
    """v1's equivalent took no user at all, so a store filter showed every
    store to somebody who could see two stores' rows."""
    control, ada, north, south = screen
    ada = grant(ada, Region, "view_region")

    class RegionPolicy(PermissionPolicy):
        view = FieldInUserSet("pk", user_set=lambda u: [north.pk])

    register_policy(Region, RegionPolicy)
    assert [label for _, label in options_for(control, ada)] == ["North"]


def test_a_control_naming_no_source_offers_nothing(db):
    """Nothing to resolve against, so the widget falls back to an input."""
    page = Page.objects.create(name="P", slug="p")
    control = PageFilter.objects.create(
        page=page, field_name="region", label="Region", widget=Widget.SELECT
    )
    assert options_for(control, None) == []


def test_a_path_that_is_not_a_field_offers_nothing(screen):
    control, ada, _, _ = screen
    control.field_name = "not_a_field"
    assert options_for(control, ada) == []


def test_the_list_is_capped(screen):
    """A cap rather than a refusal: a widget that fetches has no such limit,
    and core has no business deciding for it."""
    control, ada, north, _ = screen
    ada = grant(ada, Region, "view_region")
    Region.objects.bulk_create([Region(name=f"R{i}") for i in range(20)])
    assert len(options_for(control, ada, limit=5)) == 5

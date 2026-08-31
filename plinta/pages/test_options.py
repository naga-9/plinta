"""What a filter offers: the values present in rows the viewer can see."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from plinta.datasources.models import DataSource
from plinta.pages.models import Page, PageFilter, Widget
from plinta.pages.options import options_for
from plinta.permissions.policies import PermissionPolicy, register_policy
from plinta.permissions.rules import Owner
from tests.testapp.models import Book, Region


def grant(user, model, codename):
    ct = ContentType.objects.get_for_model(model)
    perm, _ = Permission.objects.get_or_create(
        codename=codename, content_type=ct, defaults={"name": codename}
    )
    user.user_permissions.add(perm)
    return User.objects.get(pk=user.pk)


@pytest.fixture
def shop(db):
    """Two regions, and books in only one of them."""
    north = Region.objects.create(name="North")
    south = Region.objects.create(name="South")
    empty = Region.objects.create(name="Unstocked")
    ada = User.objects.create(username="ada")
    mira = User.objects.create(username="mira")

    Book.objects.create(title="Dune", owner=ada, region=north)
    Book.objects.create(title="Emma", owner=ada, region=south)
    Book.objects.create(title="Ariel", owner=mira, region=south)

    source = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    page = Page.objects.create(name="Catalogue", slug="catalogue")

    def control(field_name, label):
        return PageFilter.objects.create(
            page=page,
            field_name=field_name,
            label=label,
            widget=Widget.MULTISELECT,
            lookup="in",
            data_source=source,
        )

    return {
        "page": page,
        "region": control("region", "Region"),
        "title": control("title", "Title"),
        "ada": grant(ada, Book, "view_book"),
        "mira": grant(mira, Book, "view_book"),
        "north": north,
        "south": south,
        "empty": empty,
    }


# --- the values that are actually there --------------------------------------


def test_only_values_present_in_the_rows_are_offered(shop):
    """A filter offers what would match something. `Unstocked` has no books,
    so offering it would be offering an empty result."""
    labels = [label for _, label in options_for(shop["region"], shop["ada"])]
    assert labels == ["North", "South"]


def test_a_viewer_with_no_rows_is_offered_nothing(shop):
    """The case that started this: head office saw every branch in the
    dropdown and no rows in the table."""
    nobody = User.objects.create(username="sam")
    assert options_for(shop["region"], nobody) == []


def test_the_row_policy_narrows_the_options(shop, policy_registry):
    """Scoping comes with the rows rather than being added to them: a value
    can only appear if a row carrying it is visible."""

    class BookPolicy(PermissionPolicy):
        view = Owner()

    register_policy(Book, BookPolicy)
    assert [label for _, label in options_for(shop["region"], shop["mira"])] == [
        "South"
    ]


# --- the cascade -------------------------------------------------------------


def test_a_sibling_selection_narrows_the_list(shop):
    """Choosing a title leaves the region filter offering only its region."""
    options = options_for(shop["region"], shop["ada"], siblings=Q(title__in=["Dune"]))
    assert [label for _, label in options] == ["North"]


def test_a_control_does_not_narrow_itself(shop):
    """`drawn_controls` excludes the control's own key. Passing it here is the
    mistake that would remove the alternatives from its own list, leaving the
    viewer unable to change their mind."""
    from plinta.pages.rendering import drawn_controls

    drawn = drawn_controls(
        shop["page"], {"region": [str(shop["north"].pk)]}, shop["ada"]
    )
    region = next(d for d in drawn if d.control.field_name == "region")
    assert [label for _, label in region.options] == ["North", "South"]


def test_the_other_control_is_narrowed_by_it(shop):
    """The same render, from the other side."""
    from plinta.pages.rendering import drawn_controls

    drawn = drawn_controls(
        shop["page"], {"region": [str(shop["north"].pk)]}, shop["ada"]
    )
    title = next(d for d in drawn if d.control.field_name == "title")
    assert [label for _, label in title.options] == ["Dune"]


# --- labels ------------------------------------------------------------------


def test_a_relation_is_labelled_by_str(shop):
    """What Django's own model choice field does, and it needs no config."""
    values = dict(options_for(shop["region"], shop["ada"]))
    assert values[str(shop["north"].pk)] == "North"


def test_options_are_sorted_by_label_not_by_key(shop):
    """Ordering foreign keys by primary key puts names in insertion order,
    which reads as no order at all."""
    labels = [label for _, label in options_for(shop["region"], shop["ada"])]
    assert labels == sorted(labels)


def test_a_value_is_a_string(shop):
    """The submitted values are strings, and the template compares them."""
    assert all(isinstance(v, str) for v, _ in options_for(shop["region"], shop["ada"]))


# --- the edges ---------------------------------------------------------------


def test_a_control_naming_no_source_offers_nothing(db):
    page = Page.objects.create(name="P", slug="p")
    control = PageFilter.objects.create(
        page=page, field_name="region", label="Region", widget=Widget.SELECT
    )
    assert options_for(control, None) == []


def test_the_list_is_capped(shop):
    """A cap rather than a refusal: a widget that fetches has no such limit."""
    assert len(options_for(shop["title"], shop["ada"], limit=2)) == 2

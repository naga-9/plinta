"""What a block hides from its viewers, and what it must not reveal."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.blocks.models import Block, SavedView
from plinta.blocks.narrowing import (
    apply_base_filter,
    apply_modifier,
    narrowing_for,
    resolved_filter,
)
from plinta.blocks.rendering import render_block
from plinta.datasources.models import DataSource, DataSourceField
from plinta.datasources.modifiers import ModifierError
from plinta.permissions.fields import sync_model
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db


@pytest.fixture
def block(db):
    ada = User.objects.create(username="ada")
    north = Region.objects.create(name="North")
    south = Region.objects.create(name="South")
    Book.objects.create(title="Dune", owner=ada, region=north, in_print=True)
    Book.objects.create(title="Emma", owner=ada, region=south, in_print=False)

    ds = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    DataSourceField.objects.create(data_source=ds, field_name="title", label="Title")
    sync_model(Book, {"title": False})

    ct = ContentType.objects.get_for_model(Book)
    for codename in ("view_book", "view_book_title"):
        perm, _ = Permission.objects.get_or_create(
            codename=codename, content_type=ct, defaults={"name": codename}
        )
        ada.user_permissions.add(perm)
    for model, codename in ((Block, "view_block"), (SavedView, "view_savedview")):
        perm, _ = Permission.objects.get_or_create(
            codename=codename,
            content_type=ContentType.objects.get_for_model(model),
            defaults={"name": codename},
        )
        ada.user_permissions.add(perm)
    ada = User.objects.get(pk=ada.pk)

    return Block.objects.create(
        name="books-table", component_type="table", data_source=ds, owner=ada
    ), ada


# --- base_filter -----------------------------------------------------------


def test_no_filter_leaves_the_rows_alone(block):
    b, ada = block
    assert apply_base_filter(Book.objects.all(), b, ada).count() == 2


def test_a_filter_narrows(block):
    b, ada = block
    b.base_filter = {"in_print": True}
    assert [x.title for x in apply_base_filter(Book.objects.all(), b, ada)] == ["Dune"]


def test_a_filter_may_traverse(block):
    b, ada = block
    b.base_filter = {"region__name": "South"}
    assert [x.title for x in apply_base_filter(Book.objects.all(), b, ada)] == ["Emma"]


def test_a_placeholder_resolves_per_viewer(block, placeholder_registry):
    b, ada = block
    placeholder_registry.register_placeholder("me", lambda ctx: ctx.user.pk)
    b.base_filter = {"owner": "__ME__"}
    assert resolved_filter(b, ada) == {"owner": ada.pk}


def test_an_unregistered_token_is_left_as_written(block, placeholder_registry):
    """It then matches nothing. Dropping the clause would widen the filter it
    was written to narrow."""
    b, ada = block
    b.base_filter = {"title": "__NOBODY__"}
    assert resolved_filter(b, ada) == {"title": "__NOBODY__"}
    assert apply_base_filter(Book.objects.all(), b, ada).count() == 0


def test_a_token_inside_a_list_resolves(block, placeholder_registry):
    b, ada = block
    placeholder_registry.register_placeholder("me", lambda ctx: ctx.user.pk)
    b.base_filter = {"owner__in": ["__ME__"]}
    assert resolved_filter(b, ada) == {"owner__in": [ada.pk]}


# --- queryset_modifier -----------------------------------------------------


def test_no_modifier_leaves_the_rows_alone(block):
    b, ada = block
    assert apply_modifier(Book.objects.all(), b, ada).count() == 2


def test_a_registered_modifier_runs(block, modifier_registry):
    b, ada = block
    modifier_registry.register_queryset_modifier(
        "in_print", lambda qs, user, **kw: qs.filter(in_print=True)
    )
    b.queryset_modifier = "in_print"
    assert [x.title for x in apply_modifier(Book.objects.all(), b, ada)] == ["Dune"]


def test_a_modifier_sees_the_viewer(block, modifier_registry):
    b, ada = block
    modifier_registry.register_queryset_modifier(
        "mine", lambda qs, user, **kw: qs.filter(owner=user)
    )
    b.queryset_modifier = "mine"
    bob = User.objects.create(username="bob")
    assert apply_modifier(Book.objects.all(), b, bob).count() == 0


def test_an_unregistered_modifier_raises(block, modifier_registry):
    """Skipping it would show every row it was meant to hide."""
    b, ada = block
    b.queryset_modifier = "gone"
    with pytest.raises(ModifierError):
        apply_modifier(Book.objects.all(), b, ada)


# --- the two together ------------------------------------------------------


def test_both_apply(block, modifier_registry):
    b, ada = block
    modifier_registry.register_queryset_modifier(
        "northern", lambda qs, user, **kw: qs.filter(region__name="North")
    )
    b.base_filter = {"in_print": True}
    b.queryset_modifier = "northern"
    assert [x.title for x in narrowing_for(b, ada)(Book.objects.all())] == ["Dune"]


def test_they_compose_rather_than_replace(block, modifier_registry):
    """A modifier narrowing to a row the filter excluded leaves nothing."""
    b, ada = block
    modifier_registry.register_queryset_modifier(
        "southern", lambda qs, user, **kw: qs.filter(region__name="South")
    )
    b.base_filter = {"in_print": True}
    b.queryset_modifier = "southern"
    assert narrowing_for(b, ada)(Book.objects.all()).count() == 0


# --- through the block -----------------------------------------------------


def test_a_base_filter_reaches_the_rendered_table(block):
    b, ada = block
    b.base_filter = {"in_print": True}
    b.save()
    out = render_block(b, ada)
    assert "Dune" in out
    assert "Emma" not in out


def test_a_modifier_reaches_the_rendered_table(block, modifier_registry):
    b, ada = block
    modifier_registry.register_queryset_modifier(
        "in_print", lambda qs, user, **kw: qs.filter(in_print=True)
    )
    b.queryset_modifier = "in_print"
    b.save()
    out = render_block(b, ada)
    assert "Dune" in out
    assert "Emma" not in out


def test_a_narrowing_receives_rows_the_policy_already_filtered(
    block, policy_registry, modifier_registry
):
    """So a modifier that only filters can never reach a hidden row."""
    from plinta.permissions import allowed
    from plinta.permissions.policies import PermissionPolicy, register_policy
    from plinta.permissions.rules import FieldEq

    class BookPolicy(PermissionPolicy):
        view = FieldEq("in_print", True)

    register_policy(Book, BookPolicy)
    modifier_registry.register_queryset_modifier(
        "titled", lambda qs, user, **kw: qs.exclude(title="")
    )
    b, ada = block
    b.queryset_modifier = "titled"
    rows = narrowing_for(b, ada)(allowed(ada, "view", Book.objects.all()))
    assert [x.title for x in rows] == ["Dune"]


def test_a_modifier_that_starts_over_defeats_the_policy(
    block, policy_registry, modifier_registry
):
    """Which is why "may narrow, must not widen" is a rule a modifier author
    keeps, not something the framework can enforce: the callable is opaque."""
    from plinta.permissions import allowed
    from plinta.permissions.policies import PermissionPolicy, register_policy
    from plinta.permissions.rules import FieldEq

    class BookPolicy(PermissionPolicy):
        view = FieldEq("in_print", True)

    register_policy(Book, BookPolicy)
    modifier_registry.register_queryset_modifier(
        "everything", lambda qs, user, **kw: Book.objects.all()
    )
    b, ada = block
    b.queryset_modifier = "everything"
    rows = narrowing_for(b, ada)(allowed(ada, "view", Book.objects.all()))
    assert rows.count() == 2

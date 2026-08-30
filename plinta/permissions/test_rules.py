"""Each rule, and the invariant that binds its two halves.

Every rule is checked twice: that its ``Q`` selects the right rows, and that
``evaluate`` agrees with that ``Q`` on every row in the table. A rule whose two
halves disagree is the one defect the pairing exists to prevent.
"""
import pytest
from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from plinta.permissions.rules import (
    DENY,
    AllowAll,
    Callable,
    FieldEq,
    FieldInUserSet,
    GroupOverlap,
    HasPerm,
    InstancePerm,
    Owner,
    ParentModelPerm,
    Public,
    UserInM2M,
)
from tests.testapp.models import Book, Note, Region

pytestmark = pytest.mark.django_db


def assert_halves_agree(rule, user, model=Book):
    """The invariant: the filter and the predicate select the same rows."""
    by_query = set(model.objects.filter(rule.to_q(user)).values_list("pk", flat=True))
    by_predicate = {row.pk for row in model.objects.all() if rule.evaluate(user, row)}
    assert by_query == by_predicate, (
        f"{rule!r} disagrees with itself: "
        f"query={sorted(by_query)} predicate={sorted(by_predicate)}"
    )
    return by_query


@pytest.fixture
def ada(db):
    return User.objects.create(username="ada")


@pytest.fixture
def bob(db):
    return User.objects.create(username="bob")


@pytest.fixture
def books(ada, bob):
    return {
        "ada": Book.objects.create(title="Dune", owner=ada),
        "bob": Book.objects.create(title="Emma", owner=bob),
        "public": Book.objects.create(title="Ulysses", owner=None),
    }


def test_owner_admits_only_the_users_own(books, ada):
    assert assert_halves_agree(Owner(), ada) == {books["ada"].pk}


def test_owner_admits_nothing_for_anonymous(books):
    assert assert_halves_agree(Owner(), AnonymousUser()) == set()


def test_owner_to_q_denies_rather_than_erroring_on_anonymous():
    """Q(owner=AnonymousUser) would fail at query time, so it never gets built."""
    assert Owner().to_q(AnonymousUser()) == DENY


def test_public_admits_rows_with_no_owner(books, ada):
    assert assert_halves_agree(Public(), ada) == {books["public"].pk}


def test_public_says_nothing_about_the_user(books, ada, bob):
    """Which is why it never stands alone for editing."""
    assert assert_halves_agree(Public(), ada) == assert_halves_agree(Public(), bob)


def test_owner_or_public_is_the_shareable_view_rule(books, ada):
    rule = Owner() | Public()
    assert assert_halves_agree(rule, ada) == {books["ada"].pk, books["public"].pk}


def test_and_narrows(books, ada):
    Book.objects.filter(pk=books["ada"].pk).update(in_print=False)
    rule = Owner() & FieldEq("in_print", True)
    assert assert_halves_agree(rule, ada) == set()


def test_not_inverts(books, ada):
    assert assert_halves_agree(~Public(), ada) == {books["ada"].pk, books["bob"].pk}


def test_field_eq(books, ada):
    Book.objects.filter(pk=books["bob"].pk).update(in_print=False)
    assert assert_halves_agree(FieldEq("in_print", True), ada) == {
        books["ada"].pk, books["public"].pk
    }


def test_allow_all(books, ada):
    assert assert_halves_agree(AllowAll(), ada) == set(
        Book.objects.values_list("pk", flat=True)
    )


def grant(user, codename, model=Book):
    """Create and grant a permission, then clear Django's per-user cache."""
    ct = ContentType.objects.get_for_model(model)
    perm, _ = Permission.objects.get_or_create(
        codename=codename, content_type=ct, defaults={"name": codename}
    )
    user.user_permissions.add(perm)
    return User.objects.get(pk=user.pk)


def test_instance_perm_is_keyed_on_the_pk(books, ada):
    ada = grant(ada, f"view_book_instance_{books['bob'].pk}")
    assert assert_halves_agree(InstancePerm("testapp", "book", "view"), ada) == {
        books["bob"].pk
    }


def test_instance_perm_denies_with_no_grants(books, ada):
    assert assert_halves_agree(InstancePerm("testapp", "book", "view"), ada) == set()


def test_a_rename_cannot_move_an_instance_grant(books, ada):
    """Keyed on pk, so the title is free to change."""
    ada = grant(ada, f"view_book_instance_{books['bob'].pk}")
    Book.objects.filter(pk=books["bob"].pk).update(title="Emma, revised")
    assert assert_halves_agree(InstancePerm("testapp", "book", "view"), ada) == {
        books["bob"].pk
    }


def test_sharing_is_additive(books, ada):
    """The owner keeps their row and gains the shared one."""
    ada = grant(ada, f"view_book_instance_{books['bob'].pk}")
    rule = Owner() | Public() | InstancePerm("testapp", "book", "view")
    assert assert_halves_agree(rule, ada) == {
        books["ada"].pk, books["bob"].pk, books["public"].pk
    }


def test_has_perm_is_all_or_nothing(books, ada):
    assert assert_halves_agree(HasPerm("testapp.publish_book"), ada) == set()
    ada = grant(ada, "publish_book")
    assert assert_halves_agree(HasPerm("testapp.publish_book"), ada) == set(
        Book.objects.values_list("pk", flat=True)
    )


def test_public_and_has_perm_is_the_publish_gate(books, ada):
    """Public content stays editable — by whoever holds the permission."""
    rule = Owner() | (Public() & HasPerm("testapp.change_book_owner"))
    assert assert_halves_agree(rule, ada) == {books["ada"].pk}
    ada = grant(ada, "change_book_owner")
    assert assert_halves_agree(rule, ada) == {books["ada"].pk, books["public"].pk}


def test_field_in_user_set_scopes_by_a_derived_set(books, ada):
    north = Region.objects.create(name="North")
    south = Region.objects.create(name="South")
    Book.objects.filter(pk=books["ada"].pk).update(region=north)
    Book.objects.filter(pk=books["bob"].pk).update(region=south)

    rule = FieldInUserSet("region", lambda u: Region.objects.filter(name="North"))
    assert assert_halves_agree(rule, ada) == {books["ada"].pk}


def test_field_in_user_set_accepts_raw_ids(books, ada):
    north = Region.objects.create(name="North")
    Book.objects.filter(pk=books["ada"].pk).update(region=north)
    rule = FieldInUserSet("region", lambda u: [north.pk])
    assert assert_halves_agree(rule, ada) == {books["ada"].pk}


def test_field_in_user_set_excludes_rows_with_no_value(books, ada):
    north = Region.objects.create(name="North")
    Book.objects.filter(pk=books["ada"].pk).update(region=north)
    rule = FieldInUserSet("region", lambda u: [north.pk])
    assert books["public"].pk not in assert_halves_agree(rule, ada)


def test_field_in_user_set_does_not_load_the_related_object(books, ada, django_assert_num_queries):
    """The id is already in memory; loading the FK would be a query per row."""
    north = Region.objects.create(name="North")
    Book.objects.filter(pk=books["ada"].pk).update(region=north)
    book = Book.objects.get(pk=books["ada"].pk)
    ids = [north.pk]

    rule = FieldInUserSet("region", lambda u: ids)
    with django_assert_num_queries(0):
        assert rule.evaluate(ada, book) is True


def test_user_in_m2m(books, ada):
    books["bob"].watchers.add(ada)
    assert assert_halves_agree(UserInM2M("watchers"), ada) == {books["bob"].pk}


def test_group_overlap(books, ada):
    readers = Group.objects.create(name="readers")
    ada.groups.add(readers)
    books["bob"].reader_groups.add(readers)
    assert assert_halves_agree(GroupOverlap("reader_groups"), ada) == {books["bob"].pk}


def test_parent_model_perm(books, ada):
    on_ada = Note.objects.create(body="x", target=books["ada"])
    Note.objects.create(body="y", content_type=ContentType.objects.get_for_model(Region),
                        object_id=1)
    ada = grant(ada, "change_book")
    rule = ParentModelPerm("change")
    assert assert_halves_agree(rule, ada, model=Note) == {on_ada.pk}


def test_parent_model_perm_denies_with_no_permissions(books, ada):
    Note.objects.create(body="x", target=books["ada"])
    assert assert_halves_agree(ParentModelPerm("change"), ada, model=Note) == set()


def test_callable_with_both_halves(books, ada):
    rule = Callable(
        q_fn=lambda u: Q(title__startswith="D"),
        eval_fn=lambda u, i: i.title.startswith("D"),
    )
    assert assert_halves_agree(rule, ada) == {books["ada"].pk}


def test_callable_derives_the_predicate_from_the_query(books, ada):
    """Correct without eval_fn, at the cost of a query per check."""
    rule = Callable(q_fn=lambda u: Q(title__startswith="D"))
    assert assert_halves_agree(rule, ada) == {books["ada"].pk}


@pytest.mark.parametrize("rule", [
    Owner(), Public(), FieldEq("in_print", True), AllowAll(),
    InstancePerm("testapp", "book", "view"),
    FieldInUserSet("region", lambda u: []),
    UserInM2M("watchers"), GroupOverlap("reader_groups"),
])
def test_every_rule_agrees_with_itself_on_an_empty_table(rule, ada):
    assert assert_halves_agree(rule, ada) == set()


def test_repr_names_the_rule_and_its_arguments():
    assert repr(Owner("created_by")) == "Owner(field='created_by')"

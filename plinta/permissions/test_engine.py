"""The two tiers, the one bypass, and what `can` and `allowed` agree on."""
import pytest
from django.contrib.auth.models import AnonymousUser, Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.permissions.engine import allowed, can, explain, fields, minted_fields
from plinta.permissions.policies import PermissionPolicy
from plinta.permissions.rules import AllowAll, HasPerm, Owner, Public
from tests.testapp.models import Book

pytestmark = pytest.mark.django_db


class BookPolicy(PermissionPolicy):
    view = Owner() | Public()
    change = Owner()


def grant(user, codename, model=Book):
    ct = ContentType.objects.get_for_model(model)
    perm, _ = Permission.objects.get_or_create(
        codename=codename, content_type=ct, defaults={"name": codename}
    )
    user.user_permissions.add(perm)
    return User.objects.get(pk=user.pk)


@pytest.fixture
def ada(db):
    return User.objects.create(username="ada")


@pytest.fixture
def root(db):
    return User.objects.create(username="root", is_superuser=True)


@pytest.fixture
def books(ada, db):
    bob = User.objects.create(username="bob")
    return {
        "ada": Book.objects.create(title="Dune", owner=ada),
        "bob": Book.objects.create(title="Emma", owner=bob),
        "public": Book.objects.create(title="Ulysses", owner=None),
    }


# --- tier 1: the model permission -----------------------------------------


def test_no_model_permission_denies_everything(books, ada, policy_registry):
    policy_registry.register_policy(Book, BookPolicy)
    assert can(ada, "view", books["ada"]) is False
    assert list(allowed(ada, "view", Book.objects.all())) == []


def test_the_model_permission_alone_is_not_enough(books, ada, policy_registry):
    """Tier 1 held, tier 2 refuses — both must pass."""
    policy_registry.register_policy(Book, BookPolicy)
    ada = grant(ada, "view_book")
    assert can(ada, "view", books["ada"]) is True
    assert can(ada, "change", books["bob"]) is False


def test_a_model_check_consults_tier_1_only(books, ada, policy_registry):
    """"May they at all?" has no row to put to a policy."""
    policy_registry.register_policy(Book, BookPolicy)
    ada = grant(ada, "view_book")
    assert can(ada, "view", Book) is True


# --- tier 2: the policy ----------------------------------------------------


def test_the_policy_narrows_rows(books, ada, policy_registry):
    policy_registry.register_policy(Book, BookPolicy)
    ada = grant(ada, "view_book")
    assert set(allowed(ada, "view", Book.objects.all()).values_list("pk", flat=True)) == {
        books["ada"].pk, books["public"].pk
    }


def test_no_policy_means_the_model_permission_decides(books, ada, policy_registry):
    """Row control is opt-in; this fails open, which is why a check reports it."""
    ada = grant(ada, "view_book")
    assert can(ada, "view", books["bob"]) is True
    assert allowed(ada, "view", Book.objects.all()).count() == 3


def test_an_undeclared_action_falls_back_to_the_model_permission(books, ada, policy_registry):
    """It does not inherit `view`, and it does not deny."""
    policy_registry.register_policy(Book, BookPolicy)
    ada = grant(ada, "delete_book")
    assert can(ada, "delete", books["bob"]) is True, "BookPolicy declares no `delete`"


def test_can_and_allowed_never_disagree(books, ada, policy_registry):
    """The invariant, one layer up from the rules."""
    policy_registry.register_policy(Book, BookPolicy)
    ada = grant(ada, "view_book")
    by_query = set(allowed(ada, "view", Book.objects.all()).values_list("pk", flat=True))
    by_check = {b.pk for b in Book.objects.all() if can(ada, "view", b)}
    assert by_query == by_check


# --- the one bypass --------------------------------------------------------


def test_a_superuser_sees_every_row_without_any_permission(books, root, policy_registry):
    policy_registry.register_policy(Book, BookPolicy)
    assert can(root, "change", books["bob"]) is True
    assert allowed(root, "view", Book.objects.all()).count() == 3


def test_the_bypass_is_not_a_rule_a_policy_could_forget(books, root, policy_registry):
    """A policy that names no superuser branch still admits one."""
    class Strict(PermissionPolicy):
        view = Owner()

    policy_registry.register_policy(Book, Strict)
    assert can(root, "view", books["bob"]) is True


# --- anonymous -------------------------------------------------------------


def test_anonymous_is_denied_before_any_rule_runs(books, policy_registry):
    """"Public" does not mean logged-out visitors."""
    policy_registry.register_policy(Book, BookPolicy)
    anon = AnonymousUser()
    assert can(anon, "view", books["public"]) is False
    assert list(allowed(anon, "view", Book.objects.all())) == []


# --- fields ----------------------------------------------------------------


def test_fields_reports_what_is_granted(ada):
    ada = grant(ada, "view_book_title")
    ada = grant(ada, "view_book_price")
    assert fields(ada, "view", Book) == {"title", "price"}


def test_an_undeclared_field_is_absent_rather_than_allowed(ada):
    """Fail-open closed: a column nobody minted is denied."""
    ada = grant(ada, "view_book_title")
    assert "cost" not in fields(ada, "view", Book)


def test_fields_separates_view_from_change(ada):
    ada = grant(ada, "view_book_price")
    ada = grant(ada, "change_book_title")
    assert fields(ada, "view", Book) == {"price"}
    assert fields(ada, "change", Book) == {"title"}


def test_a_superuser_gets_every_minted_field(root, ada):
    grant(ada, "view_book_title")
    grant(ada, "view_book_price")
    assert fields(root, "view", Book) == {"title", "price"}


def test_anonymous_gets_no_fields():
    assert fields(AnonymousUser(), "view", Book) == set()


def test_minted_fields_reads_the_permission_table(ada):
    grant(ada, "view_book_title")
    assert minted_fields("view", Book) == {"title"}


# --- explain ---------------------------------------------------------------


def test_explain_names_the_missing_model_permission(books, ada, policy_registry):
    policy_registry.register_policy(Book, BookPolicy)
    decision = explain(ada, "view", books["ada"])
    assert decision.allowed is False
    assert "testapp.view_book" in decision.reason
    assert decision.model_permission is False


def test_explain_traces_which_branch_refused(books, ada, policy_registry):
    policy_registry.register_policy(Book, BookPolicy)
    ada = grant(ada, "view_book")
    decision = explain(ada, "view", books["bob"])

    assert decision.allowed is False
    assert decision.policy == "BookPolicy"
    rendered = str(decision)
    assert "Owner(field='owner')" in rendered
    assert "Public(field='owner')" in rendered
    assert rendered.count("deny") >= 3, "the branch and both its children"


def test_the_trace_names_a_combinator_without_repeating_its_subtree(books, ada, policy_registry):
    """A trace that reprints the whole tree at every level is unreadable."""
    policy_registry.register_policy(Book, BookPolicy)
    ada = grant(ada, "view_book")
    rendered = str(explain(ada, "view", books["bob"]))
    assert "OR" in rendered
    assert "_Or(" not in rendered
    assert rendered.count("Owner(field='owner')") == 1


def test_explain_traces_which_branch_admitted(books, ada, policy_registry):
    policy_registry.register_policy(Book, BookPolicy)
    ada = grant(ada, "view_book")
    decision = explain(ada, "view", books["public"])
    assert decision.allowed is True
    assert "allow" in str(decision)


def test_explain_reports_a_missing_policy(books, ada, policy_registry):
    ada = grant(ada, "view_book")
    assert "no policy registered" in explain(ada, "view", books["bob"]).reason


def test_explain_reports_an_undeclared_action(books, ada, policy_registry):
    policy_registry.register_policy(Book, BookPolicy)
    ada = grant(ada, "delete_book")
    assert "declares no rule for 'delete'" in explain(ada, "delete", books["bob"]).reason


def test_explain_agrees_with_can(books, ada, policy_registry):
    """A diagnostic that contradicted the decision would be worse than none."""
    policy_registry.register_policy(Book, BookPolicy)
    ada = grant(ada, "view_book")
    for book in Book.objects.all():
        assert explain(ada, "view", book).allowed == can(ada, "view", book)


def test_explain_short_circuits_for_a_superuser(books, root, policy_registry):
    policy_registry.register_policy(Book, BookPolicy)
    decision = explain(root, "view", books["bob"])
    assert decision.allowed is True and decision.reason == "superuser"


def test_a_deeper_tree_traces_every_level(books, ada, policy_registry):
    class Deep(PermissionPolicy):
        view = Owner() | (Public() & HasPerm("testapp.publish_book"))

    policy_registry.register_policy(Book, Deep)
    ada = grant(ada, "view_book")
    rendered = str(explain(ada, "view", books["public"]))
    assert "HasPerm" in rendered and "Public" in rendered


def test_allow_all_policy_admits_everything(books, ada, policy_registry):
    class Open(PermissionPolicy):
        view = AllowAll()

    policy_registry.register_policy(Book, Open)
    ada = grant(ada, "view_book")
    assert allowed(ada, "view", Book.objects.all()).count() == 3

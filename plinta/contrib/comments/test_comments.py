"""Comments, and the event they emit rather than the app they used to call."""
import pathlib

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.contrib.comments.capabilities import commented_models
from plinta.contrib.comments.models import Comment
from plinta.contrib.comments.services import (
    CommentDenied,
    edit,
    post,
    resolve_mentions,
    thread,
    withdraw,
)
from plinta.events import signals
from plinta.permissions import allowed
from plinta.permissions.policies import PermissionPolicy, register_policy
from plinta.permissions.rules import Owner
from tests.contribapp.models import Article, Memo

pytestmark = pytest.mark.django_db


@pytest.fixture
def people(db):
    ada = User.objects.create(username="ada")
    bob = User.objects.create(username="bob")
    ct = ContentType.objects.get_for_model(Article)
    comment_ct = ContentType.objects.get_for_model(Comment)
    for user in (ada, bob):
        for codename, content_type in (
            ("view_article", ct),
            ("view_comment", comment_ct),
            ("add_comment", comment_ct),
            ("change_comment", comment_ct),
            ("delete_comment", comment_ct),
        ):
            perm, _ = Permission.objects.get_or_create(
                codename=codename, content_type=content_type,
                defaults={"name": codename},
            )
            user.user_permissions.add(perm)
    return User.objects.get(pk=ada.pk), User.objects.get(pk=bob.pk)


@pytest.fixture
def book(db):
    return Article.objects.create(title="Dune")


# --- it emits, and calls nobody --------------------------------------------


def test_it_imports_no_other_contrib_package():
    """Calling notifications from here is what made notifications mandatory
    for anybody who wanted comments."""
    package = pathlib.Path(__file__).resolve().parent
    reaching = [
        path.name
        for path in package.glob("*.py")
        if not path.name.startswith("test_")
        and "plinta.contrib." in path.read_text(encoding="utf-8").replace(
            "plinta.contrib.comments", ""
        )
    ]
    assert reaching == []


def test_posting_emits_the_event(people, book, listen):
    seen = {}
    ada, _ = people
    listen(signals.comment_posted, lambda sender, **kw: seen.update(kw))
    post(book, "A fine book", ada)
    assert seen["obj"] == book
    assert seen["body"] == "A fine book"
    assert seen["actor"] == ada


def test_the_row_exists_when_the_event_fires(people, book, listen):
    """A listener that reads the comment finds one."""
    seen = {}
    ada, _ = people
    listen(
        signals.comment_posted,
        lambda sender, metadata=None, **kw: seen.update(
            exists=Comment.objects.filter(pk=(metadata or {}).get("comment_id")).exists()
        ),
    )
    post(book, "A fine book", ada)
    assert seen["exists"]


def test_a_notification_can_be_built_on_it(people, book):
    """The end of the chain that used to be an import: comments emits,
    notifications subscribes, and neither names the other."""
    from plinta.contrib.notifications.models import Notification
    from plinta.contrib.notifications.registry import (
        _registry,
        register_notification,
    )

    ada, bob = people
    saved = dict(_registry)
    _registry.clear()
    try:
        register_notification(
            "book_commented", "contribapp.article", "comment_posted",
            recipients=lambda obj, **kw: [bob],
            title=lambda obj, body="", **kw: f"New comment: {body}",
        )
        post(book, "A fine book", ada)
        assert Notification.objects.get().title == "New comment: A fine book"
    finally:
        _registry.clear()
        _registry.update(saved)


# --- posting ---------------------------------------------------------------


def test_a_comment_is_attached_to_its_row(people, book):
    ada, _ = people
    comment = post(book, "Hello", ada)
    assert comment.target == book
    assert list(Comment.objects.on(book)) == [comment]


def test_an_empty_comment_is_refused(people, book):
    ada, _ = people
    with pytest.raises(CommentDenied, match="needs a body"):
        post(book, "   ", ada)


def test_commenting_needs_sight_of_the_row(people, book, policy_registry):
    """Commenting is reading a record out loud, so it cannot be open to
    somebody who may not read it."""
    class ArticlePolicy(PermissionPolicy):
        view = Owner("owner")

    register_policy(Article, ArticlePolicy)
    _, bob = people
    with pytest.raises(CommentDenied, match="may not see"):
        post(book, "Hello", bob)


def test_a_reply_is_grouped_under_its_parent(people, book):
    ada, bob = people
    first = post(book, "A question", ada)
    reply = post(book, "An answer", bob, reply_to=first)
    assert reply.reply_to == first
    assert list(first.replies.all()) == [reply]


def test_a_reply_may_reply_to_a_reply(people, book):
    """Stored as sent. Re-parenting it here would silently move a remark
    somebody aimed at a particular reply; how deep a thread is *drawn* is a
    template's decision."""
    ada, bob = people
    first = post(book, "A question", ada)
    reply = post(book, "An answer", bob, reply_to=first)
    deeper = post(book, "A follow-up", ada, reply_to=reply)
    assert deeper.reply_to == reply


def test_depth_is_readable_for_whoever_draws_it(people, book):
    ada, bob = people
    first = post(book, "A question", ada)
    reply = post(book, "An answer", bob, reply_to=first)
    deeper = post(book, "A follow-up", ada, reply_to=reply)
    assert [c.depth() for c in (first, reply, deeper)] == [0, 1, 2]


# --- privacy ---------------------------------------------------------------


def test_a_comment_with_no_owner_is_public(people, book):
    ada, bob = people
    post(book, "for everyone", ada)
    assert len(thread(book, bob)) == 1


def test_an_owned_comment_is_private(people, book):
    ada, bob = people
    post(book, "just me", ada, owner=ada)
    assert thread(book, bob) == []
    assert len(thread(book, ada)) == 1


def test_a_private_comment_may_name_who_sees_it(people, book):
    ada, bob = people
    post(book, "you and me", ada, owner=ada, visible_to=[bob])
    assert len(thread(book, bob)) == 1


def test_a_private_comment_may_name_a_group(people, book):
    from django.contrib.auth.models import Group

    ada, bob = people
    editors = Group.objects.create(name="Editors")
    bob.groups.add(editors)
    post(book, "for the editors", ada, owner=ada, visible_to_groups=[editors])
    assert len(thread(book, User.objects.get(pk=bob.pk))) == 1


def test_somebody_outside_the_group_still_cannot_see_it(people, book):
    from django.contrib.auth.models import Group

    ada, bob = people
    editors = Group.objects.create(name="Editors")
    post(book, "for the editors", ada, owner=ada, visible_to_groups=[editors])
    assert thread(book, bob) == []


def test_making_it_private_is_not_the_same_as_writing_it(people, book):
    """change and delete are the author's; owner is about who may read."""
    ada, bob = people
    comment = post(book, "mine", ada, owner=bob)
    with pytest.raises(CommentDenied):
        edit(comment, "yours", bob)
    edit(comment, "still mine", ada)


def test_a_private_thread_and_a_public_one_coexist(people, book):
    ada, bob = people
    post(book, "public", ada)
    post(book, "private", ada, owner=ada)
    assert [c.body for c in thread(book, bob)] == ["public"]
    assert len(thread(book, ada)) == 2


# --- mentions --------------------------------------------------------------


@pytest.mark.parametrize(
    "body,expected",
    [
        ("hello @ada", ["ada"]),
        ("@ada and @bob", ["ada", "bob"]),
        ("@ada @ada", ["ada"]),
        ("no mention here", []),
        ("write to ada@example.com", []),
        ("@ada, thanks", ["ada"]),
    ],
)
def test_mentions_are_extracted(body, expected):
    assert Comment(body=body).mentions() == expected


def test_a_mention_is_resolved_to_a_user(people):
    ada, _ = people
    assert resolve_mentions(["ada"]) == [ada]


def test_a_mention_of_nobody_is_ignored(people):
    """A typo is not an error: refusing to post is a worse answer than nobody
    being told."""
    assert resolve_mentions(["nobody_at_all"]) == []


def test_mentions_travel_on_the_event(people, book, listen):
    seen = {}
    ada, bob = people
    listen(signals.comment_posted, lambda sender, **kw: seen.update(kw))
    post(book, "over to @bob", ada)
    assert seen["metadata"]["mentioned"] == [bob.pk]


def test_this_app_does_not_decide_what_a_mention_means(people, book):
    """It resolves who was named and stops there."""
    ada, bob = people
    post(book, "over to @bob", ada)
    from plinta.contrib.notifications.models import Notification

    assert not Notification.objects.exists()


# --- editing and withdrawing -----------------------------------------------


def test_an_author_may_edit_their_own(people, book):
    ada, _ = people
    comment = post(book, "frist", ada)
    edit(comment, "first", ada)
    comment.refresh_from_db()
    assert comment.body == "first"
    assert comment.edited_at is not None


def test_somebody_else_may_not(people, book):
    ada, bob = people
    comment = post(book, "mine", ada)
    with pytest.raises(CommentDenied, match="somebody else"):
        edit(comment, "yours", bob)


def test_an_edit_emits_nothing(people, book, listen):
    """A correction is not a new remark, and announcing one would notify a
    thread every time somebody fixed a typo."""
    seen = []
    ada, _ = people
    comment = post(book, "frist", ada)
    listen(signals.comment_posted, lambda **kw: seen.append(1))
    edit(comment, "first", ada)
    assert seen == []


def test_withdrawing_keeps_the_row(people, book):
    """A thread with a hole in it reads as a bug."""
    ada, _ = people
    comment = post(book, "never mind", ada)
    withdraw(comment, ada)
    comment.refresh_from_db()
    assert comment.is_deleted
    assert Comment.objects.on(book).count() == 1
    assert Comment.objects.on(book).alive().count() == 0


def test_withdrawing_is_idempotent(people, book):
    ada, _ = people
    comment = post(book, "never mind", ada)
    withdraw(comment, ada)
    first = comment.deleted_at
    withdraw(comment, ada)
    assert comment.deleted_at == first


def test_somebody_else_may_not_withdraw_it(people, book):
    ada, bob = people
    comment = post(book, "mine", ada)
    with pytest.raises(CommentDenied):
        withdraw(comment, bob)


# --- reading the thread ----------------------------------------------------


def test_the_thread_is_oldest_first(people, book):
    ada, bob = people
    post(book, "one", ada)
    post(book, "two", bob)
    assert [c.body for c in thread(book, ada)] == ["one", "two"]


def test_a_thread_belongs_to_one_row(people, book):
    ada, _ = people
    other = Article.objects.create(title="Emma")
    post(book, "here", ada)
    assert thread(other, ada) == []


def test_without_the_permission_the_thread_is_empty(people, book):
    ada, _ = people
    post(book, "here", ada)
    stranger = User.objects.create(username="nobody")
    assert allowed(stranger, "view", Comment.objects.all()).count() == 0


# --- opting in -------------------------------------------------------------


def test_a_model_opts_in_with_a_generic_relation():
    """One line in the consumer's own models, and nothing registered anywhere."""
    assert Article in commented_models()
    assert Memo not in commented_models()


def test_the_capability_offers_the_section():
    from plinta.blocks.capabilities import matrix

    result = matrix([Article, Memo])
    assert "comments" in [c.name for c in result[Article]]
    assert result[Memo] == []


def test_it_does_not_apply_to_an_unsaved_row():
    from plinta.blocks.capabilities import for_object

    assert [c.name for c in for_object(Article())] == []

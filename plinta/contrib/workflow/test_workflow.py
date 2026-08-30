"""A state machine by registration, and the three gates on every move."""
import pathlib

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.contrib.workflow import guards, permissions, services
from plinta.contrib.workflow.models import Workflow, WorkflowState, WorkflowTransition
from plinta.contrib.workflow.services import TransitionDenied
from plinta.events import signals
from tests.contribapp.models import Article, Memo

pytestmark = pytest.mark.django_db


@pytest.fixture
def guard_registry():
    saved = dict(guards._registry)
    guards._registry.clear()
    yield guards
    guards._registry.clear()
    guards._registry.update(saved)


@pytest.fixture
def flow(db):
    """Draft to review to published, over a model that inherits nothing."""
    workflow = Workflow.objects.create(
        name="Editorial",
        code="editorial",
        content_type=ContentType.objects.get_for_model(Article),
        state_field="state",
    )
    draft = WorkflowState.objects.create(
        workflow=workflow, code="draft", label="Draft", is_initial=True, order=0
    )
    review = WorkflowState.objects.create(
        workflow=workflow, code="review", label="In review", order=1
    )
    published = WorkflowState.objects.create(
        workflow=workflow, code="published", label="Published", is_final=True, order=2
    )
    submit = WorkflowTransition.objects.create(
        workflow=workflow, from_state=draft, to_state=review, label="Submit"
    )
    publish = WorkflowTransition.objects.create(
        workflow=workflow, from_state=review, to_state=published, label="Publish"
    )
    states = {"draft": draft, "review": review, "published": published}
    return workflow, states, {"submit": submit, "publish": publish}


@pytest.fixture
def editor(db):
    ada = User.objects.create(username="ada")
    ct = ContentType.objects.get_for_model(Article)
    for codename in ("change_article", "view_article"):
        perm, _ = Permission.objects.get_or_create(
            codename=codename, content_type=ct, defaults={"name": codename}
        )
        ada.user_permissions.add(perm)
    return User.objects.get(pk=ada.pk)


def allow(user, from_code, to_code):
    """Grant one transition's permission."""
    perm = Permission.objects.get(
        content_type=ContentType.objects.get_for_model(Article),
        codename=permissions.codename(Article, from_code, to_code),
    )
    user.user_permissions.add(perm)
    return User.objects.get(pk=user.pk)


# --- registration, not inheritance -----------------------------------------


def test_the_model_inherits_nothing(flow):
    """Its state is a column it declared itself."""
    assert not any("workflow" in base.__name__.lower() for base in Article.__mro__[1:])
    assert Article._meta.get_field("state").__class__.__name__ == "CharField"


def test_the_state_is_an_ordinary_column(flow):
    """So it sorts and filters like any other, which a foreign key to this
    app's table would not."""
    Article.objects.create(title="A", state="review")
    Article.objects.create(title="B", state="draft")
    assert [a.title for a in Article.objects.order_by("state")] == ["B", "A"]


def test_a_workflow_is_found_by_content_type(flow):
    article = Article.objects.create(title="A")
    assert services.workflow_for(article).code == "editorial"


def test_a_model_with_no_workflow_has_none(flow):
    assert services.workflow_for(Memo.objects.create(title="M")) is None


def test_a_new_row_starts_in_the_initial_state(flow):
    assert services.set_initial(Article(title="A")) == "draft"


def test_a_row_that_already_has_one_is_left_alone(flow):
    assert services.set_initial(Article(title="A", state="review")) == "review"


# --- the permission per transition -----------------------------------------


def test_saving_a_transition_mints_its_permission(flow):
    assert Permission.objects.filter(
        codename=permissions.codename(Article, "draft", "review")
    ).exists()


def test_it_is_separable_from_change(flow, editor):
    """Which is the whole reason a transition carries its own permission."""
    assert editor.has_perm("contribapp.change_article")
    assert not editor.has_perm(permissions.full_codename(Article, "draft", "review"))


def test_renaming_a_state_keeps_the_grants(flow, editor):
    """A grant points at a permission's primary key, so recreating one drops
    every grant on it silently."""
    _, states, _ = flow
    editor = allow(editor, "draft", "review")
    before = Permission.objects.get(
        codename=permissions.codename(Article, "draft", "review")
    ).pk

    states["draft"].code = "new_draft"
    states["draft"].save()

    after = Permission.objects.get(
        codename=permissions.codename(Article, "new_draft", "review")
    )
    assert after.pk == before
    assert User.objects.get(pk=editor.pk).has_perm(
        permissions.full_codename(Article, "new_draft", "review")
    )


def test_renaming_a_state_renames_every_transition_touching_it(flow):
    _, states, _ = flow
    states["review"].code = "checking"
    states["review"].save()
    assert Permission.objects.filter(
        codename=permissions.codename(Article, "draft", "checking")
    ).exists()
    assert Permission.objects.filter(
        codename=permissions.codename(Article, "checking", "published")
    ).exists()


def test_deleting_a_transition_removes_its_permission(flow):
    _, _, transitions = flow
    transitions["submit"].delete()
    assert not Permission.objects.filter(
        codename=permissions.codename(Article, "draft", "review")
    ).exists()


def test_rebuild_is_the_backstop_for_a_bulk_import(flow):
    """bulk_create fires no post_save at all."""
    workflow, _, _ = flow
    Permission.objects.filter(
        codename=permissions.codename(Article, "draft", "review")
    ).delete()
    assert permissions.rebuild(workflow) == [
        permissions.codename(Article, "draft", "review")
    ]


# --- the three gates -------------------------------------------------------


def test_without_the_transition_permission_it_is_refused(flow, editor):
    _, _, transitions = flow
    article = Article.objects.create(title="A", state="draft")
    with pytest.raises(TransitionDenied, match="permission"):
        services.execute(article, transitions["submit"], editor)


def test_without_change_on_the_row_it_is_refused(flow, editor, policy_registry):
    from plinta.permissions.policies import PermissionPolicy, register_policy
    from plinta.permissions.rules import Owner

    class ArticlePolicy(PermissionPolicy):
        change = Owner("owner")

    register_policy(Article, ArticlePolicy)
    _, _, transitions = flow
    editor = allow(editor, "draft", "review")
    article = Article.objects.create(title="A", state="draft")
    with pytest.raises(TransitionDenied, match="may not change"):
        services.execute(article, transitions["submit"], editor)


def test_a_guard_may_refuse_with_a_reason(flow, editor, guard_registry):
    """Which is what a screen shows instead of a button that does nothing."""
    guard_registry.register_guard(
        "has_body", check=lambda obj, **kw: bool(obj.body) or "Write something first."
    )
    _, _, transitions = flow
    transitions["submit"].guard = "has_body"
    transitions["submit"].save()
    editor = allow(editor, "draft", "review")
    article = Article.objects.create(title="A", state="draft")
    with pytest.raises(TransitionDenied, match="Write something first"):
        services.execute(article, transitions["submit"], editor)


def test_a_satisfied_guard_permits(flow, editor, guard_registry):
    guard_registry.register_guard("has_body", check=lambda obj, **kw: bool(obj.body))
    _, _, transitions = flow
    transitions["submit"].guard = "has_body"
    transitions["submit"].save()
    editor = allow(editor, "draft", "review")
    article = Article.objects.create(title="A", state="draft", body="words")
    assert services.execute(article, transitions["submit"], editor).state == "review"


def test_a_guard_that_raises_refuses(flow, editor, guard_registry):
    """Permitting on error would wave through the move it was written to stop."""
    guard_registry.register_guard("broken", check=lambda obj, **kw: 1 / 0)
    _, _, transitions = flow
    transitions["submit"].guard = "broken"
    transitions["submit"].save()
    editor = allow(editor, "draft", "review")
    article = Article.objects.create(title="A", state="draft")
    with pytest.raises(TransitionDenied, match="could not be checked"):
        services.execute(article, transitions["submit"], editor)


def test_a_guard_nothing_registered_refuses(flow, editor):
    """The condition was written down because somebody meant it to hold."""
    _, _, transitions = flow
    transitions["submit"].guard = "gone"
    transitions["submit"].save()
    editor = allow(editor, "draft", "review")
    article = Article.objects.create(title="A", state="draft")
    with pytest.raises(guards.GuardError):
        services.execute(article, transitions["submit"], editor)


# --- making the move -------------------------------------------------------


def test_a_permitted_move_changes_the_state(flow, editor):
    _, _, transitions = flow
    editor = allow(editor, "draft", "review")
    article = Article.objects.create(title="A", state="draft")
    services.execute(article, transitions["submit"], editor)
    article.refresh_from_db()
    assert article.state == "review"


def test_it_emits_the_event(flow, editor, listen):
    seen = {}
    _, _, transitions = flow
    editor = allow(editor, "draft", "review")
    listen(signals.state_changed, lambda sender, **kw: seen.update(kw))
    article = Article.objects.create(title="A", state="draft")
    services.execute(article, transitions["submit"], editor, source="ui")
    assert (seen["from_state"], seen["to_state"]) == ("draft", "review")
    assert seen["actor"] == editor
    assert seen["source"] == "ui"


def test_the_event_carries_string_codes_not_rows(flow, editor, listen):
    """Schema-pure, so a listener never imports this app to read it."""
    seen = {}
    _, _, transitions = flow
    editor = allow(editor, "draft", "review")
    listen(signals.state_changed, lambda sender, **kw: seen.update(kw))
    services.execute(
        Article.objects.create(title="A", state="draft"), transitions["submit"], editor
    )
    assert isinstance(seen["from_state"], str)


def test_the_row_is_saved_before_the_event(flow, editor, listen):
    seen = {}
    _, _, transitions = flow
    editor = allow(editor, "draft", "review")
    listen(
        signals.state_changed,
        lambda sender, obj, **kw: seen.update(
            stored=Article.objects.get(pk=obj.pk).state
        ),
    )
    services.execute(
        Article.objects.create(title="A", state="draft"), transitions["submit"], editor
    )
    assert seen["stored"] == "review"


def test_a_refused_move_changes_nothing(flow, editor):
    _, _, transitions = flow
    article = Article.objects.create(title="A", state="draft")
    with pytest.raises(TransitionDenied):
        services.execute(article, transitions["submit"], editor)
    article.refresh_from_db()
    assert article.state == "draft"


def test_a_move_from_the_wrong_state_is_refused(flow, editor):
    """The row moved on since the button was drawn."""
    _, _, transitions = flow
    editor = allow(editor, "review", "published")
    article = Article.objects.create(title="A", state="draft")
    with pytest.raises(TransitionDenied, match="moved on"):
        services.execute(article, transitions["publish"], editor)


# --- what a screen is offered ----------------------------------------------


def test_the_moves_out_of_this_state_are_offered(flow, editor):
    editor = allow(editor, "draft", "review")
    article = Article.objects.create(title="A", state="draft")
    offered = services.available(article, editor)
    assert [m.transition.to_state.code for m in offered] == ["review"]
    assert offered[0].permitted


def test_a_refused_move_is_offered_with_its_reason(flow, editor):
    """Rather than hidden — a move that vanishes reads as a missing feature."""
    article = Article.objects.create(title="A", state="draft")
    moves = services.available(article, editor)
    assert len(moves) == 1
    assert not moves[0].permitted
    assert "permission" in moves[0].reason


def test_a_final_state_offers_nothing(flow, editor):
    article = Article.objects.create(title="A", state="published")
    assert services.available(article, editor) == []


def test_a_model_with_no_workflow_offers_nothing(flow, editor):
    assert services.available(Memo.objects.create(title="M"), editor) == []


# --- history, when audit is there ------------------------------------------


def test_the_history_reads_the_audit_trail(flow, editor):
    """Which records state_changed like any other write, so this app needs no
    history table of its own."""
    _, _, transitions = flow
    editor = allow(editor, "draft", "review")
    article = Article.objects.create(title="A", state="draft")
    services.execute(article, transitions["submit"], editor)
    entries = services.history(article)
    assert len(entries) == 1
    assert entries[0].changes == {"state": ["draft", "review"]}


def test_it_never_imports_audit_at_module_scope():
    """The read is declared as `enhances` and reached behind a check, so the
    state machine runs with that app absent."""
    package = pathlib.Path(__file__).resolve().parent
    offenders = [
        path.name
        for path in package.glob("*.py")
        if not path.name.startswith("test_")
        and any(
            line.startswith(("from plinta.contrib.audit", "import plinta.contrib.audit"))
            for line in path.read_text(encoding="utf-8").splitlines()
        )
    ]
    assert offenders == []

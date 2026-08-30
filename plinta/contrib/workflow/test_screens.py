"""The status panel, the transition button, and the state chip."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.blocks.capabilities import for_object, matrix
from plinta.contrib.workflow import permissions
from plinta.contrib.workflow.models import Workflow, WorkflowState, WorkflowTransition
from plinta.contrib.workflow.templatetags.plinta_workflow import workflow_panel
from plinta.renderers.fields import render_field
from tests.contribapp.models import Article, Memo

pytestmark = pytest.mark.django_db


@pytest.fixture
def flow(db):
    workflow = Workflow.objects.create(
        name="Editorial", code="editorial",
        content_type=ContentType.objects.get_for_model(Article),
        state_field="state",
    )
    draft = WorkflowState.objects.create(
        workflow=workflow, code="draft", label="Draft", is_initial=True,
        colour="pl-chip--warning",
    )
    review = WorkflowState.objects.create(
        workflow=workflow, code="review", label="In review", order=1
    )
    submit = WorkflowTransition.objects.create(
        workflow=workflow, from_state=draft, to_state=review, label="Submit"
    )
    return workflow, submit


@pytest.fixture
def editor(db, client):
    ada = User.objects.create_user(username="ada", password="x")  # noqa: S106
    ct = ContentType.objects.get_for_model(Article)
    for codename in ("change_article", "view_article"):
        perm, _ = Permission.objects.get_or_create(
            codename=codename, content_type=ct, defaults={"name": codename}
        )
        ada.user_permissions.add(perm)
    ada = User.objects.get(pk=ada.pk)
    client.force_login(ada)
    return ada


def allow(user, from_code, to_code):
    perm = Permission.objects.get(
        content_type=ContentType.objects.get_for_model(Article),
        codename=permissions.codename(Article, from_code, to_code),
    )
    user.user_permissions.add(perm)
    return User.objects.get(pk=user.pk)


# --- the capability --------------------------------------------------------


def test_a_governed_model_gets_the_panel(flow):
    assert "workflow" in [c.name for c in matrix([Article])[Article]]


def test_an_ungoverned_one_does_not(flow):
    assert "workflow" not in [c.name for c in matrix([Memo])[Memo]]


def test_it_does_not_apply_to_an_unsaved_row(flow):
    """Nothing to move, and nowhere to record having moved it."""
    assert "workflow" not in [c.name for c in for_object(Article())]


def test_which_models_are_governed_comes_from_the_rows(flow):
    """A workflow is data, so which models have one is a question for the
    database rather than a registry in code."""
    workflow, _ = flow
    assert "workflow" in [c.name for c in matrix([Article])[Article]]
    workflow.is_active = False
    workflow.save()
    assert "workflow" not in [c.name for c in matrix([Article])[Article]]


# --- the panel -------------------------------------------------------------


def test_the_panel_says_where_the_row_is(flow, editor):
    article = Article.objects.create(title="A", state="draft")
    assert workflow_panel(article, editor).state.label == "Draft"


def test_the_panel_offers_the_moves(flow, editor):
    editor = allow(editor, "draft", "review")
    article = Article.objects.create(title="A", state="draft")
    panel = workflow_panel(article, editor)
    assert [m.label for m in panel.moves] == ["Submit"]
    assert panel.moves[0].permitted


def test_a_refused_move_is_offered_with_its_reason(flow, editor):
    article = Article.objects.create(title="A", state="draft")
    move = workflow_panel(article, editor).moves[0]
    assert not move.permitted
    assert move.reason


def test_a_model_with_no_workflow_gets_an_empty_panel(flow, editor):
    """So the template draws nothing rather than guarding every line."""
    assert workflow_panel(Memo.objects.create(title="M"), editor).workflow is None


def test_an_unsaved_row_gets_an_empty_panel(flow, editor):
    assert workflow_panel(Article(title="A"), editor).workflow is None


def test_the_panel_carries_the_history(flow, editor):
    from plinta.contrib.workflow import services

    workflow, submit = flow
    editor = allow(editor, "draft", "review")
    article = Article.objects.create(title="A", state="draft")
    services.execute(article, submit, editor)
    assert len(workflow_panel(article, editor).history) == 1


# --- making the move from a screen -----------------------------------------


def test_pressing_the_button_moves_the_row(flow, editor, client):
    workflow, submit = flow
    editor = allow(editor, "draft", "review")
    client.force_login(editor)
    article = Article.objects.create(title="A", state="draft")

    response = client.post(
        f"/workflow/transition/{submit.pk}/", {"record": article.pk, "next": "/"}
    )
    article.refresh_from_db()
    assert response.status_code == 302
    assert article.state == "review"


def test_a_get_does_not_move_it(flow, editor, client):
    """A write behind a GET is a link a crawler can follow."""
    workflow, submit = flow
    editor = allow(editor, "draft", "review")
    client.force_login(editor)
    article = Article.objects.create(title="A", state="draft")
    assert client.get(f"/workflow/transition/{submit.pk}/").status_code == 405
    article.refresh_from_db()
    assert article.state == "draft"


def test_a_refusal_says_why(flow, editor, client):
    workflow, submit = flow
    article = Article.objects.create(title="A", state="draft")
    from django.contrib.messages import get_messages

    response = client.post(
        f"/workflow/transition/{submit.pk}/", {"record": article.pk, "next": "/"}
    )
    told = [str(m) for m in get_messages(response.wsgi_request)]
    assert any("permission" in m for m in told)
    article.refresh_from_db()
    assert article.state == "draft"


def test_the_row_is_found_through_the_workflows_model(flow, editor, client):
    """So a caller cannot name a transition on one model and a row on
    another."""
    workflow, submit = flow
    editor = allow(editor, "draft", "review")
    client.force_login(editor)
    memo = Memo.objects.create(title="M")
    assert client.post(
        f"/workflow/transition/{submit.pk}/", {"record": memo.pk, "next": "/"}
    ).status_code == 404


def test_an_anonymous_visitor_cannot(flow, client):
    workflow, submit = flow
    article = Article.objects.create(title="A", state="draft")
    client.logout()
    response = client.post(
        f"/workflow/transition/{submit.pk}/", {"record": article.pk}
    )
    assert response.status_code == 302
    article.refresh_from_db()
    assert article.state == "draft"


# --- the state chip --------------------------------------------------------


class Field:
    renderer = "workflow_state"
    field_name = "state"


def test_a_state_renders_as_its_label(flow):
    article = Article.objects.create(title="A", state="draft")
    assert "Draft" in render_field("draft", Field(), obj=article)


def test_it_carries_the_states_colour(flow):
    """A class name, so core's tokens draw it and this app names no palette."""
    article = Article.objects.create(title="A", state="draft")
    assert "pl-chip--warning" in render_field("draft", Field(), obj=article)


def test_a_code_nothing_describes_still_shows(flow):
    """A state removed from a workflow leaves rows holding its code, and the
    code is more useful than nothing."""
    article = Article.objects.create(title="A", state="archived")
    assert "archived" in render_field("archived", Field(), obj=article)


def test_an_empty_state_draws_nothing(flow):
    article = Article.objects.create(title="A", state="")
    assert render_field("", Field(), obj=article) == ""

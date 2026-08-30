"""A logged-in viewer reaching a page, through the whole stack."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.blocks.models import Block, SavedView
from plinta.datasources.models import DataSource, DataSourceField
from plinta.pages.models import (
    FilterSet,
    MenuGroup,
    MenuSection,
    Page,
    PageBlock,
    PageFilter,
    PageFilterPreference,
    PageType,
)
from plinta.permissions.fields import sync_model
from plinta.shell.links import register_shell_link, visible_links
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db

MODELS = (Block, SavedView, Page, FilterSet)


@pytest.fixture
def screen(db, client):
    ada = User.objects.create_user(username="ada", password="secret")  # noqa: S106
    north = Region.objects.create(name="North")
    Book.objects.create(title="Dune", owner=ada, region=north, in_print=True)
    Book.objects.create(title="Emma", owner=ada, region=north, in_print=False)

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
    for model in MODELS:
        codename = f"view_{model._meta.model_name}"
        perm, _ = Permission.objects.get_or_create(
            codename=codename,
            content_type=ContentType.objects.get_for_model(model),
            defaults={"name": codename},
        )
        ada.user_permissions.add(perm)

    section = MenuSection.objects.create(name="Reference")
    group = MenuGroup.objects.create(section=section, name="Catalog")
    page = Page.objects.create(
        name="Catalog", slug="catalog", owner=ada, menu_group=group
    )
    block = Block.objects.create(
        name="books-table", component_type="table_plinta", data_source=ds, owner=ada
    )
    PageBlock.objects.create(page=page, block=block, column=0, row=0, width=6, height=4)

    client.force_login(User.objects.get(pk=ada.pk))
    return page, block, User.objects.get(pk=ada.pk)


# --- the gate --------------------------------------------------------------


def test_an_anonymous_visitor_is_sent_to_login(screen, client):
    page, _, _ = screen
    client.logout()
    response = client.get(page.get_absolute_url())
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


def test_the_login_page_renders(client):
    response = client.get("/accounts/login/")
    assert response.status_code == 200
    assert "Sign in" in response.content.decode()


def test_the_login_page_is_reachable_without_logging_in(client):
    assert client.get("/accounts/login/").status_code == 200


# --- a page ----------------------------------------------------------------


def test_a_viewer_reaches_their_page(screen, client):
    page, _, _ = screen
    response = client.get(page.get_absolute_url())
    assert response.status_code == 200


def test_the_page_draws_its_rows(screen, client):
    page, _, _ = screen
    body = client.get(page.get_absolute_url()).content.decode()
    assert "Dune" in body and "Emma" in body


def test_the_grid_carries_the_stored_position(screen, client):
    """Straight into custom properties, so layout needs no JavaScript."""
    page, _, _ = screen
    body = client.get(page.get_absolute_url()).content.decode()
    assert "--col: 0; --row: 0; --w: 6; --h: 4" in body


def test_the_slug_is_decorative(screen, client):
    """A rename must not break a link someone shared."""
    page, _, _ = screen
    assert client.get(f"/pages/{page.pk}-anything-at-all/").status_code == 200


def test_a_page_may_be_reached_by_id_alone(screen, client):
    page, _, _ = screen
    assert client.get(f"/pages/{page.pk}/").status_code == 200


def test_someone_elses_page_is_not_found(screen, client):
    """A 404, not a 403: saying it exists but is not yours is a disclosure."""
    page, _, _ = screen
    bob = User.objects.create_user(username="bob", password="secret")  # noqa: S106
    client.force_login(bob)
    assert client.get(page.get_absolute_url()).status_code == 404


def test_an_inactive_page_is_not_found(screen, client):
    page, _, _ = screen
    Page.objects.filter(pk=page.pk).update(is_active=False)
    assert client.get(page.get_absolute_url()).status_code == 404


def test_a_page_that_does_not_exist_is_not_found(screen, client):
    assert client.get("/pages/9999-nope/").status_code == 404


# --- the chrome ------------------------------------------------------------


def test_the_menu_lists_the_page(screen, client):
    page, _, _ = screen
    body = client.get(page.get_absolute_url()).content.decode()
    assert "Reference" in body and "Catalog" in body


def test_the_stylesheets_are_linked(screen, client):
    page, _, _ = screen
    body = client.get(page.get_absolute_url()).content.decode()
    assert "plinta/css/tokens.css" in body
    assert "plinta/css/plinta.css" in body


def test_the_viewer_is_named(screen, client):
    page, _, _ = screen
    assert "ada" in client.get(page.get_absolute_url()).content.decode()


# --- filters ---------------------------------------------------------------


def test_a_declared_filter_narrows_the_page(screen, client):
    page, _, _ = screen
    PageFilter.objects.create(page=page, field_name="in_print", label="In print")
    body = client.get(page.get_absolute_url(), {"in_print": "True"}).content.decode()
    assert "Dune" in body and "Emma" not in body


def test_an_undeclared_parameter_is_ignored(screen, client):
    """The bar is what the page exposes; a query string is not."""
    page, _, _ = screen
    body = client.get(page.get_absolute_url(), {"in_print": "True"}).content.decode()
    assert "Emma" in body


def test_a_filter_is_remembered(screen, client):
    page, _, ada = screen
    PageFilter.objects.create(page=page, field_name="in_print", label="In print")
    client.get(page.get_absolute_url(), {"in_print": "True"})
    assert PageFilterPreference.objects.get(page=page, owner=ada).values == {
        "in_print": "True"
    }


def test_a_remembered_filter_applies_on_return(screen, client):
    page, _, ada = screen
    PageFilter.objects.create(page=page, field_name="in_print", label="In print")
    PageFilterPreference.objects.create(
        page=page, owner=ada, values={"in_print": "True"}
    )
    body = client.get(page.get_absolute_url()).content.decode()
    assert "Emma" not in body


def test_clearing_forgets_them(screen, client):
    page, _, ada = screen
    PageFilter.objects.create(page=page, field_name="in_print", label="In print")
    PageFilterPreference.objects.create(
        page=page, owner=ada, values={"in_print": "True"}
    )
    response = client.get(page.get_absolute_url(), {"reset": "1"})
    assert response.status_code == 302
    assert PageFilterPreference.objects.get(page=page, owner=ada).values == {}


def test_the_filter_bar_appears_only_when_declared(screen, client):
    page, _, _ = screen
    assert "pl-filters" not in client.get(page.get_absolute_url()).content.decode()
    PageFilter.objects.create(page=page, field_name="in_print", label="In print")
    assert "pl-filters" in client.get(page.get_absolute_url()).content.decode()


# --- degradations ----------------------------------------------------------


def test_an_uninstalled_component_leaves_an_empty_slot(screen, client):
    page, block, _ = screen
    Block.objects.filter(pk=block.pk).update(component_type="heatmap")
    body = client.get(page.get_absolute_url()).content.decode()
    assert "pl-slot--empty" in body
    assert "pl-grid__item" in body


def test_a_broken_block_says_so_and_the_page_survives(screen, client, settings):
    settings.DEBUG = False
    page, block, _ = screen
    Block.objects.filter(pk=block.pk).update(config={"page_sise": 1})
    response = client.get(page.get_absolute_url())
    assert response.status_code == 200
    assert "pl-alert--danger" in response.content.decode()


# --- a custom-template page ------------------------------------------------


def test_a_custom_template_page_renders_its_template(screen, client):
    page, _, _ = screen
    Page.objects.filter(pk=page.pk).update(
        page_type=PageType.CUSTOM_TEMPLATE, template_name="plinta/shell/base.html"
    )
    assert client.get(page.get_absolute_url()).status_code == 200


# --- fixed links -----------------------------------------------------------


def test_a_fixed_link_is_shown_to_a_holder(screen, client, shell_link_registry):
    page, _, ada = screen
    register_shell_link(
        "blocks", "Blocks", url_name="plinta:login", permission="plinta_blocks.view_block"
    )
    assert [link.name for link in visible_links(ada)] == ["blocks"]


def test_a_fixed_link_is_hidden_from_everyone_else(screen, client, shell_link_registry):
    """Gated by the shell, because no Page row governs a screen that is a view."""
    register_shell_link(
        "sources", "Data Sources", url_name="plinta:login",
        permission="plinta_datasources.view_datasource",
    )
    _, _, ada = screen
    assert visible_links(ada) == []


# --- sorting and paging, end to end ----------------------------------------


def test_a_heading_is_a_sort_link(screen, client):
    page, _, _ = screen
    body = client.get(page.get_absolute_url()).content.decode()
    assert "pl-table__sort" in body


def test_clicking_it_reorders_the_rows(screen, client):
    page, _, block_ = screen
    placement = page.placements.get()
    body = client.get(
        page.get_absolute_url(), {f"b{placement.pk}_sort": "-title"}
    ).content.decode()
    assert body.index("Emma") < body.index("Dune")


def test_two_tables_sort_independently(screen, client):
    """Each placement's parameters are prefixed with its id, so one heading
    does not move the other table."""
    page, block, _ = screen
    second = PageBlock.objects.create(page=page, block=block, order=1)
    first = page.placements.order_by("order").first()
    body = client.get(page.get_absolute_url()).content.decode()
    assert f"b{first.pk}_sort=title" in body
    assert f"b{second.pk}_sort=title" in body


def test_paging_is_a_link(screen, client):
    page, block, _ = screen
    Block.objects.filter(pk=block.pk).update(config={"page_size": 1})
    placement = page.placements.get()
    body = client.get(page.get_absolute_url()).content.decode()
    assert "pl-pager" in body
    assert f"b{placement.pk}_page=2" in body


def test_the_second_page_shows_the_next_row(screen, client):
    page, block, _ = screen
    Block.objects.filter(pk=block.pk).update(
        config={"page_size": 1, "sort": [{"field": "title"}]}
    )
    placement = page.placements.get()
    body = client.get(
        page.get_absolute_url(), {f"b{placement.pk}_page": "2"}
    ).content.decode()
    assert "Emma" in body and "<td>Dune</td>" not in body


def test_a_filter_survives_a_sort(screen, client):
    """A link that dropped it would look like it worked and quietly widen the
    result."""
    page, _, _ = screen
    PageFilter.objects.create(page=page, field_name="in_print", label="In print")
    placement = page.placements.get()
    body = client.get(page.get_absolute_url(), {"in_print": "True"}).content.decode()
    assert "in_print=True" in body
    assert f"b{placement.pk}_sort=title" in body


def test_no_javascript_draws_the_table(screen, client):
    """The whole claim: a viewer's page loads no vendor script at all."""
    page, _, _ = screen
    body = client.get(page.get_absolute_url()).content.decode()
    assert "tabulator" not in body.lower()
    assert body.count("<script") == 1  # theme-toggle, and nothing else


# --- detail pages ----------------------------------------------------------


@pytest.fixture
def detail(screen, client):
    """The same page, bound to one record."""
    page, block, ada = screen
    Page.objects.filter(pk=page.pk).update(
        page_type=PageType.DETAIL,
        primary_data_source=block.data_source,
        context_param="book",
    )
    page.refresh_from_db()
    page.placements.update(context_filter={"pk": "__RECORD__"})
    return page, Book.objects.get(title="Dune"), ada


def test_a_detail_page_shows_its_record(detail, client):
    page, book, _ = detail
    body = client.get(f"/pages/{page.pk}-catalog/{book.pk}/").content.decode()
    assert "Dune" in body
    assert "Emma" not in body


def test_the_record_reaches_a_placements_filter(detail, client):
    """Through __RECORD__ in its context_filter, so one placement serves every
    record the page shows."""
    page, book, _ = detail
    other = Book.objects.get(title="Emma")
    body = client.get(f"/pages/{page.pk}-catalog/{other.pk}/").content.decode()
    assert "Emma" in body
    assert "<td>Dune</td>" not in body


def test_a_detail_page_without_a_record_is_not_found(detail, client):
    page, _, _ = detail
    assert client.get(page.get_absolute_url()).status_code == 404


def test_a_record_that_does_not_exist_is_not_found(detail, client):
    page, _, _ = detail
    assert client.get(f"/pages/{page.pk}-catalog/9999/").status_code == 404


def test_a_record_the_viewer_may_not_see_is_not_found(detail, client, policy_registry):
    """A 404, not a 403: saying a record exists but is not yours is itself a
    disclosure."""
    from plinta.permissions.policies import PermissionPolicy, register_policy
    from plinta.permissions.rules import FieldEq

    class BookPolicy(PermissionPolicy):
        view = FieldEq("in_print", False)

    register_policy(Book, BookPolicy)
    page, book, _ = detail
    assert client.get(f"/pages/{page.pk}-catalog/{book.pk}/").status_code == 404


def test_the_record_may_arrive_as_a_query_parameter(detail, client):
    """A detail page reached from somewhere else often arrives as ?book=7."""
    page, book, _ = detail
    response = client.get(page.get_absolute_url(), {"book": book.pk})
    assert response.status_code == 200
    assert "Dune" in response.content.decode()


def test_a_dashboard_ignores_a_record(screen, client):
    """__RECORD__ resolves to None there, so a page that never asked for one
    is unaffected."""
    page, _, _ = screen
    assert client.get(page.get_absolute_url()).status_code == 200


def test_a_page_naming_no_model_cannot_bind_one(detail, client):
    page, book, _ = detail
    Page.objects.filter(pk=page.pk).update(primary_data_source=None)
    assert client.get(f"/pages/{page.pk}-catalog/{book.pk}/").status_code == 404


# --- capability sections ---------------------------------------------------


def test_a_dashboard_draws_no_sections(screen, client):
    page, _, _ = screen
    assert client.get(page.get_absolute_url()).context["capabilities"] == []


def test_a_detail_page_draws_what_the_apps_contribute(
    detail, client, capability_registry
):
    """Which is how comments, attachments and the rest reach a screen — none
    of them named anywhere in core."""
    capability_registry.register_capability(
        "notes", "Notes", template="plinta/pages/block.html"
    )
    page, book, _ = detail
    body = client.get(f"/pages/{page.pk}-catalog/{book.pk}/").content.decode()
    assert "pl-card" in body


def test_a_capability_that_declines_this_row_is_absent(
    detail, client, capability_registry
):
    capability_registry.register_capability(
        "notes", "Notes", applies_to=lambda obj, user=None, **kw: False
    )
    page, book, _ = detail
    response = client.get(f"/pages/{page.pk}-catalog/{book.pk}/")
    assert response.context["capabilities"] == []


def test_with_no_contrib_installed_there_are_no_sections(detail, client):
    page, book, _ = detail
    response = client.get(f"/pages/{page.pk}-catalog/{book.pk}/")
    assert response.context["capabilities"] == []

"""A logged-in viewer reaching a page, through the whole stack."""
import re

import pytest
from django.contrib.auth.models import Permission, User
from django.db.models import Q
from django.test import RequestFactory
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
    assert [link.label for link in visible_links(ada)] == ["Blocks"]


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
    """The whole claim: a viewer's page loads no vendor script at all.

    Counting scripts would only measure how many behaviours the shell has
    grown. What must stay true is that every one of them is ours and none
    comes from a CDN.
    """
    page, _, _ = screen
    body = client.get(page.get_absolute_url()).content.decode()

    assert "tabulator" not in body.lower()
    sources = re.findall(r'<script[^>]*src="([^"]+)"', body)
    assert sources, "the shell loads no script at all"
    assert all(src.startswith("/static/plinta/js/") for src in sources), sources


# --- the menu toggle --------------------------------------------------------


def test_the_toggle_names_the_thing_it_controls(screen, client):
    """`aria-controls` must point at an id that exists, or it points nowhere.

    The button shipped before anything listened to it; this is the pair of
    assertions that would have noticed.
    """
    page, _, _ = screen
    body = client.get(page.get_absolute_url()).content.decode()

    assert "data-plinta-sidebar-toggle" in body
    assert 'aria-controls="pl-sidebar"' in body
    assert 'id="pl-sidebar"' in body


def test_the_collapse_is_stamped_before_paint(screen, client):
    """`sidebar.js` must not be deferred.

    A module or a `defer` runs after the document is parsed, so a remembered
    collapse would draw the menu and then take it away.
    """
    page, _, _ = screen
    body = client.get(page.get_absolute_url()).content.decode()

    tag = next(line for line in body.splitlines() if "sidebar.js" in line)
    assert "type=\"module\"" not in tag
    assert "defer" not in tag


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


def test_a_link_may_carry_a_count(screen, client, shell_link_registry):
    """The one thing a link cannot say on its own, and the realistic want —
    "Reports 3" — without opening the nav to arbitrary markup."""
    page, _, ada = screen
    register_shell_link(
        "reports", "Reports", url_name="plinta:login",
        permission="plinta_blocks.view_block", badge=lambda user: 3,
    )
    assert [link.badge for link in visible_links(ada)] == [3]


def test_a_count_of_zero_draws_nothing(screen, client, shell_link_registry):
    """A badge saying "0" is worse than no badge."""
    page, _, ada = screen
    register_shell_link(
        "reports", "Reports", url_name="plinta:login",
        permission="plinta_blocks.view_block", badge=lambda user: 0,
    )
    assert [link.badge for link in visible_links(ada)] == [None]


def test_a_broken_count_does_not_take_down_the_menu(
    screen, client, shell_link_registry, caplog
):
    page, _, ada = screen
    register_shell_link(
        "reports", "Reports", url_name="plinta:login",
        permission="plinta_blocks.view_block", badge=lambda user: 1 / 0,
    )
    assert [link.badge for link in visible_links(ada)] == [None]
    assert "badge for" in caplog.text


def test_a_links_icon_is_drawn(screen, client, shell_link_registry):
    """Core's own set, inline. No font, no request, nothing to fail."""
    page, _, ada = screen
    register_shell_link(
        "reports", "Reports", url_name="plinta:login",
        permission="plinta_blocks.view_block", icon="file",
    )
    body = client.get(page.get_absolute_url()).content.decode()
    assert '<svg class="pl-icon"' in body
    assert "stroke=\"currentColor\"" in body


def test_a_pages_menu_icon_is_drawn(screen, client):
    page, _, _ = screen
    Page.objects.filter(pk=page.pk).update(menu_icon="book")
    body = client.get(page.get_absolute_url()).content.decode()
    assert '<svg class="pl-icon"' in body


def test_a_consumers_own_set_is_used_when_named(screen, client, icon_registry):
    """`set:name`, so a project already loading a font keeps using it."""
    from django.utils.html import format_html

    from plinta.utils.icons import register_icon_set, register_defaults

    register_defaults()
    register_icon_set(
        "bi", render=lambda name, **kw: format_html('<i class="bi bi-{}"></i>', name)
    )
    page, _, _ = screen
    Page.objects.filter(pk=page.pk).update(menu_icon="bi:book")
    body = client.get(page.get_absolute_url()).content.decode()
    assert '<i class="bi bi-book"></i>' in body


def test_an_unknown_icon_leaves_a_gap_not_a_box(screen, client):
    """It sits beside a label that already says what the thing is."""
    page, _, _ = screen
    Page.objects.filter(pk=page.pk).update(menu_icon="nonesuch")
    body = client.get(page.get_absolute_url()).content.decode()
    assert page.name in body
    assert "nonesuch" not in body


def test_an_unregistered_set_draws_nothing(screen, client):
    page, _, _ = screen
    Page.objects.filter(pk=page.pk).update(menu_icon="fa:book")
    assert "fa:book" not in client.get(page.get_absolute_url()).content.decode()


def test_the_shells_own_glyphs_are_icons_too(screen, client):
    """`≡` and `◐` were literal characters."""
    page, _, _ = screen
    body = client.get(page.get_absolute_url()).content.decode()
    assert "≡" not in body and "◐" not in body
    assert body.count('<svg class="pl-icon"') >= 2


# --- saved filter sets -----------------------------------------------------


def test_the_picker_is_absent_when_there_are_none(screen, client):
    """A control offering nothing to choose is furniture."""
    page, _, _ = screen
    PageFilter.objects.create(page=page, field_name="in_print", label="In print")
    assert "pl-filterset" not in client.get(page.get_absolute_url()).content.decode()


def test_the_sets_this_viewer_may_see_are_offered(screen, client):
    page, _, ada = screen
    bob = User.objects.create(username="bob")
    FilterSet.objects.create(page=page, name="Mine", owner=ada, values={})
    FilterSet.objects.create(page=page, name="Shared", owner=None, values={})
    FilterSet.objects.create(page=page, name="Bob's", owner=bob, values={})

    body = client.get(page.get_absolute_url()).content.decode()
    assert "Mine" in body and "Shared" in body
    assert "Bob&#x27;s" not in body and "Bob's" not in body


def test_a_public_set_is_marked_as_shared(screen, client):
    page, _, _ = screen
    FilterSet.objects.create(page=page, name="Shared", owner=None, values={})
    assert "(shared)" in client.get(page.get_absolute_url()).content.decode()


def test_choosing_one_applies_its_values(screen, client):
    page, _, ada = screen
    PageFilter.objects.create(page=page, field_name="in_print", label="In print")
    saved = FilterSet.objects.create(
        page=page, name="In print", owner=ada, values={"in_print": "True"}
    )
    body = client.get(page.get_absolute_url(), {"filterset": saved.pk}).content.decode()
    assert "Dune" in body and "Emma" not in body


def test_the_chosen_one_stays_selected(screen, client):
    page, _, ada = screen
    saved = FilterSet.objects.create(page=page, name="Mine", owner=ada, values={})
    response = client.get(page.get_absolute_url(), {"filterset": saved.pk})
    assert response.context["chosen_set"] == saved
    assert "selected" in response.content.decode()


def test_somebody_elses_set_is_not_applied(screen, client):
    """Matched against what they may see rather than fetched by id — the id is
    guessable, and a refusal would confirm it exists."""
    page, _, _ = screen
    bob = User.objects.create(username="bob")
    PageFilter.objects.create(page=page, field_name="in_print", label="In print")
    saved = FilterSet.objects.create(
        page=page, name="Bob's", owner=bob, values={"in_print": "True"}
    )
    body = client.get(page.get_absolute_url(), {"filterset": saved.pk}).content.decode()
    assert "Emma" in body


def test_choosing_one_is_remembered(screen, client):
    page, _, ada = screen
    PageFilter.objects.create(page=page, field_name="in_print", label="In print")
    saved = FilterSet.objects.create(
        page=page, name="In print", owner=ada, values={"in_print": "True"}
    )
    client.get(page.get_absolute_url(), {"filterset": saved.pk})
    assert PageFilterPreference.objects.get(page=page, owner=ada).values == {
        "in_print": "True"
    }


def test_a_set_wins_over_the_controls(screen, client):
    """Choosing a set is the more deliberate act, so it wins over whatever the
    controls were showing when it was chosen."""
    page, _, ada = screen
    PageFilter.objects.create(page=page, field_name="in_print", label="In print")
    saved = FilterSet.objects.create(
        page=page, name="In print", owner=ada, values={"in_print": "True"}
    )
    body = client.get(
        page.get_absolute_url(), {"filterset": saved.pk, "in_print": "False"}
    ).content.decode()
    assert "Dune" in body and "Emma" not in body


def test_a_sets_placeholders_resolve(screen, client, placeholder_registry):
    page, _, ada = screen
    placeholder_registry.register_placeholder("me", lambda ctx: ctx.user.pk)
    PageFilter.objects.create(page=page, field_name="owner", label="Owner")
    saved = FilterSet.objects.create(
        page=page, name="Mine", owner=ada, values={"owner": "__ME__"}
    )
    assert client.get(
        page.get_absolute_url(), {"filterset": saved.pk}
    ).status_code == 200


def test_filterset_is_not_treated_as_a_column(screen, client):
    """It is the bar's own parameter, not a field the page declares."""
    page, _, ada = screen
    saved = FilterSet.objects.create(page=page, name="Mine", owner=ada, values={})
    response = client.get(page.get_absolute_url(), {"filterset": saved.pk})
    assert "filterset" not in response.context["filter_values"]


def test_a_registered_stylesheet_reaches_the_page(screen, client, stylesheet_registry):
    """The whole point: a component that ships a template can ship its CSS.

    Drawn after core's own, so it can rely on the tokens and the shared
    primitives already being defined.
    """
    from plinta.utils.assets import register_stylesheet

    register_stylesheet("plinta/heatmap/heatmap.css")
    page, _, _ = screen
    body = client.get(page.get_absolute_url()).content.decode()

    assert "/static/plinta/heatmap/heatmap.css" in body
    assert body.index("plinta.css") < body.index("heatmap.css")


# --- multi-valued controls --------------------------------------------------


@pytest.fixture
def multi(screen):
    """The catalogue page, with a multi-select over the region relation."""
    from plinta.pages.models import PageFilter, Widget

    page, block, _ = screen
    PageFilter.objects.create(
        page=page,
        field_name="region",
        label="Region",
        widget=Widget.MULTISELECT,
        lookup="in",
        data_source=block.data_source,
    )
    # A scalar control beside it, so the two paths are compared on one page.
    PageFilter.objects.create(page=page, field_name="title", label="Title")
    return page


def test_a_repeated_key_carries_every_value(multi, client):
    """`GET[name]` keeps only the last, so a two-option selection silently
    filtered on whichever happened to be last in the form."""
    from plinta.shell.views import submitted_filters

    request = RequestFactory().get(multi.get_absolute_url(), {"region": ["1", "2"]})
    assert submitted_filters(request, multi) == {"region": ["1", "2"]}


def test_a_single_valued_control_stays_scalar(multi, client):
    """Only a widget that says it is multiple gets a list."""
    from plinta.shell.views import submitted_filters

    request = RequestFactory().get(multi.get_absolute_url(), {"title": "Dune"})
    assert submitted_filters(request, multi)["title"] == "Dune"


def test_clearing_a_multiselect_clears_the_filter(multi, client):
    """The hidden field keeps the key present, so an empty selection reaches
    the view as [] and drops the filter rather than reapplying the default."""
    from plinta.pages.rendering import filter_q

    assert filter_q(multi, {"region": []}, None) == Q()


def test_several_values_become_an_in_lookup(multi, client):
    from plinta.pages.rendering import filter_q

    assert filter_q(multi, {"region": ["1", "2"]}, None) == Q(region__in=["1", "2"])


def test_the_bar_draws_the_widget_s_own_template(multi, client):
    body = client.get(multi.get_absolute_url()).content.decode()
    assert "<select" in body and "multiple" in body
    # The hidden companion, without which clearing is impossible.
    assert '<input type="hidden" name="region" value="">' in body


# --- the live cascade --------------------------------------------------------


def test_the_options_endpoint_answers_with_every_control(multi, client):
    """So the bar can narrow while somebody is choosing, rather than only
    after they apply. Applying first to find out what to apply is the wrong
    order."""
    import json

    response = client.get(f"/pages/{multi.pk}/filter-options/")
    assert response.status_code == 200
    assert "region" in json.loads(response.content)


def test_it_narrows_by_the_other_controls(multi, client, screen):
    """The same narrowing a reload does, at the moment of choosing."""
    import json

    page, block, _ = screen
    body = json.loads(
        client.get(f"/pages/{multi.pk}/filter-options/", {"title": "Dune"}).content
    )
    assert [label for _, label in body.get("region", [])] == ["North"]


def test_a_control_is_not_narrowed_by_itself(multi, client, screen):
    """Its own selection is excluded, or the first choice could not be
    changed."""
    import json

    body = json.loads(
        client.get(f"/pages/{multi.pk}/filter-options/", {"region": ["1"]}).content
    )
    assert len(body.get("region", [])) >= 1


def test_a_page_the_viewer_may_not_see_is_a_404(multi, client, django_user_model):
    """The endpoint answers with values from rows; the gate must be the page's
    own, not merely being signed in."""
    other = django_user_model.objects.create_user("intruder", password="x")  # noqa: S106
    client.force_login(other)
    assert client.get(f"/pages/{multi.pk}/filter-options/").status_code == 404


def test_anonymous_is_redirected_not_answered(multi):
    """`@login_required` on a plain view redirects, which is what a browser
    wants — the reason fragments left ninja (§15.4)."""
    from django.test import Client

    response = Client().get(f"/pages/{multi.pk}/filter-options/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


def test_the_bar_carries_the_endpoint(multi, client):
    body = client.get(multi.get_absolute_url()).content.decode()
    assert f'data-options-url="/pages/{multi.pk}/filter-options/"' in body


# --- the operator picker -----------------------------------------------------


@pytest.fixture
def picker(screen):
    """The catalogue's title filter, offering three operators."""
    from plinta.pages.models import Lookup

    page, _, _ = screen
    PageFilter.objects.create(
        page=page, field_name="title", label="Title", lookup=Lookup.ICONTAINS,
        allowed_lookups=["icontains", "exact", "istartswith"],
    )
    return page


def test_the_picker_is_drawn_beside_the_input(picker, client):
    body = client.get(picker.get_absolute_url()).content.decode()
    assert 'name="title__op"' in body
    assert ">starts with<" in body


def test_choosing_an_operator_changes_the_query(picker, client):
    body = client.get(
        picker.get_absolute_url(), {"title": "du", "title__op": "istartswith"}
    ).content.decode()
    assert "Dune" in body and "Emma" not in body


def test_an_operator_off_the_list_is_refused_end_to_end(picker, client):
    """Not an error — the author's own operator stands. The path is never
    assembled from input, so there is nothing to inject into."""
    body = client.get(
        picker.get_absolute_url(), {"title": "une", "title__op": "regex"}
    ).content.decode()
    # `icontains` matched, so the regex operator was not honoured.
    assert "Dune" in body


def test_a_traversal_cannot_be_smuggled_through_the_operator(picker, client):
    """v1 accepted `author__user__password__startswith` because it validated
    the lookup and not the path."""
    response = client.get(
        picker.get_absolute_url(),
        {"title": "a", "title__op": "owner__password__startswith"},
    )
    assert response.status_code == 200


def test_the_chosen_operator_is_remembered(picker, client, screen):
    """It is part of the control's value, so it survives into a saved set and
    a remembered preference like any other choice."""
    from plinta.pages.models import PageFilterPreference

    _, _, ada = screen
    client.get(picker.get_absolute_url(), {"title": "du", "title__op": "exact"})
    stored = PageFilterPreference.objects.get(page=picker, owner=ada).values
    assert stored["title"] == {"op": "exact", "value": "du"}


# --- the bar is the site's, the header is the page's -------------------------


def test_the_topbar_does_not_name_the_page(screen, client):
    """It says the same thing on every screen, so nothing in it has to know
    which one is open. The page's own header carries the title."""
    page, _, _ = screen
    body = client.get(page.get_absolute_url()).content.decode()
    bar = body[body.index("pl-topbar"):body.index("pl-sidebar")]
    assert page.name not in bar


def test_the_page_header_carries_the_title(screen, client):
    page, _, _ = screen
    body = client.get(page.get_absolute_url()).content.decode()
    assert f"<h1>{page.name}</h1>" in body


def test_the_brand_is_inside_the_bar(screen, client):
    """One band across the top rather than two strips with a seam."""
    page, _, _ = screen
    body = client.get(page.get_absolute_url()).content.decode()
    bar = body[body.index("<header"):body.index("</header>")]
    assert "pl-topbar__brand" in bar


def test_a_saved_set_is_a_page_action(screen, client, django_user_model):
    """It applies to the whole page, so it belongs in the header rather than
    among the controls it replaces."""
    from plinta.pages.models import FilterSet

    page, _, ada = screen
    FilterSet.objects.create(page=page, name="Mine", owner=ada, values={})
    body = client.get(page.get_absolute_url()).content.decode()
    header = body[body.index("pl-page__header"):body.index("pl-grid")]
    assert 'name="filterset"' in header


# --- tabs --------------------------------------------------------------------


@pytest.fixture
def tabbed(screen):
    page, _, _ = screen
    Page.objects.filter(pk=page.pk).update(
        tabs=[{"key": "sales", "label": "Sales"}, {"key": "stock", "label": "Stock"}]
    )
    return Page.objects.get(pk=page.pk)


def test_tabs_are_links_not_an_aria_tablist(tabbed, client):
    """Choosing one loads a new document, and the tab pattern promises the
    opposite — that the panel is already here and switching is instant."""
    body = client.get(tabbed.get_absolute_url()).content.decode()
    assert 'role="tablist"' not in body
    assert 'role="tab"' not in body
    assert 'aria-label="Sections of this page"' in body


def test_the_current_tab_is_marked(tabbed, client):
    """It looked identical to the others: `.pl-btn.is-active` was a class
    nothing styled."""
    import re

    body = client.get(tabbed.get_absolute_url(), {"tab": "stock"}).content.decode()
    strip = body[body.index("pl-tabs"):body.index("pl-grid")]
    marked = re.findall(r'href="\?tab=(\w+)"[^>]*aria-current="page"', strip, re.S)
    assert marked == ["stock"]


def test_no_tab_chosen_marks_none(tabbed, client):
    body = client.get(tabbed.get_absolute_url()).content.decode()
    strip = body[body.index("pl-tabs"):body.index("pl-grid")]
    assert 'aria-current="page"' not in strip


def test_the_strip_is_a_list(tabbed, client):
    """Two links are two items; a screen reader says how many there are."""
    body = client.get(tabbed.get_absolute_url()).content.decode()
    strip = body[body.index("pl-tabs"):body.index("pl-grid")]
    assert strip.count('class="pl-tabs__item"') == 2


# --- the card's own shell ----------------------------------------------------


def test_a_component_declares_its_padding(screen, client):
    """A table draws to the edge; the card's padding would double the cell's
    at the rim while leaving the middle unchanged."""
    page, _, _ = screen
    body = client.get(page.get_absolute_url()).content.decode()
    assert "pl-card__body--none" in body


def test_the_blocks_description_is_shown(screen, client):
    """It was read nowhere. A card saying what it shows is worth the line."""
    page, block, _ = screen
    Block.objects.filter(pk=block.pk).update(description="Every title we carry")
    body = client.get(page.get_absolute_url()).content.decode()
    assert "Every title we carry" in body


def test_a_block_with_no_views_offers_no_picker(screen, client):
    """A lone control showing one option is furniture."""
    page, _, _ = screen
    body = client.get(page.get_absolute_url()).content.decode()
    assert "_view" not in body


def test_a_saved_view_can_be_chosen(screen, client):
    """`render_block(view=…)` existed and nothing passed one, so a non-default
    view was unreachable however it was offered."""
    page, block, ada = screen
    SavedView.objects.create(
        block=block, name="Titles only", owner=ada, config={"columns": ["title"]}
    )
    placement = page.placements.get()

    body = client.get(page.get_absolute_url()).content.decode()
    assert f'name="b{placement.pk}_view"' in body

    chosen = client.get(
        page.get_absolute_url(), {f"b{placement.pk}_view": "999999"}
    ).content.decode()
    # A view nobody owns is not found rather than refused: the id is
    # guessable, and a refusal would confirm it exists.
    assert re.search(r"<th[ >]", chosen)


def test_choosing_a_view_changes_what_is_drawn(screen, client):
    page, block, ada = screen
    # A second column, so narrowing to one has something to narrow.
    DataSourceField.objects.create(
        data_source=block.data_source, field_name="region__name", label="Region"
    )
    sync_model(Book, {"title": False, "region__name": False})
    ct = ContentType.objects.get_for_model(Book)
    perm, _ = Permission.objects.get_or_create(
        codename="view_book_region__name", content_type=ct,
        defaults={"name": "view_book_region__name"},
    )
    ada.user_permissions.add(perm)
    client.force_login(User.objects.get(pk=ada.pk))

    view = SavedView.objects.create(
        block=block, name="Titles only", owner=ada, config={"columns": ["title"]}
    )
    placement = page.placements.get()

    def headings(body):
        # `<thead>` also starts with `<th`, so match the tag rather than the
        # prefix.
        return len(re.findall(r"<th[ >]", body))

    both = client.get(page.get_absolute_url()).content.decode()
    narrowed = client.get(
        page.get_absolute_url(), {f"b{placement.pk}_view": view.pk}
    ).content.decode()
    assert headings(both) == 2
    assert headings(narrowed) == 1


def test_two_blocks_choose_views_independently(screen, client):
    """The parameter carries the placement's prefix, the same rule sort and
    page numbers follow."""
    page, block, ada = screen
    SavedView.objects.create(block=block, name="A", owner=ada, config={})
    second = PageBlock.objects.create(page=page, block=block, order=1)
    body = client.get(page.get_absolute_url()).content.decode()
    first = page.placements.exclude(pk=second.pk).get()
    assert f'name="b{first.pk}_view"' in body
    assert f'name="b{second.pk}_view"' in body


def test_two_placements_of_one_block_open_on_different_views(screen, client):
    """The question this was built for: the same table twice, each starting
    where its placement says."""
    page, block, ada = screen
    DataSourceField.objects.create(
        data_source=block.data_source, field_name="region__name", label="Region"
    )
    sync_model(Book, {"title": False, "region__name": False})
    ct = ContentType.objects.get_for_model(Book)
    perm, _ = Permission.objects.get_or_create(
        codename="view_book_region__name", content_type=ct,
        defaults={"name": "view_book_region__name"},
    )
    ada.user_permissions.add(perm)
    client.force_login(User.objects.get(pk=ada.pk))

    narrow = SavedView.objects.create(
        block=block, name="Titles", owner=None, config={"columns": ["title"]}
    )
    first = page.placements.get()
    PageBlock.objects.filter(pk=first.pk).update(default_view=narrow)
    second = PageBlock.objects.create(page=page, block=block, order=1)

    body = client.get(page.get_absolute_url()).content.decode()
    tables = body.split('<div class="pl-table-wrap">')[1:]
    counts = [len(re.findall(r"<th[ >]", table)) for table in tables]
    assert counts == [1, 2], "each placement opens on its own default"
    assert second.default_view_id is None


def test_a_placement_may_not_name_another_blocks_view(screen):
    """A view carries a config shaped by one component; another block's would
    merge keys that component does not declare."""
    from django.core.exceptions import ValidationError

    page, block, ada = screen
    other = Block.objects.create(
        name="other", component_type="table_plinta",
        data_source=block.data_source, owner=ada,
    )
    theirs = SavedView.objects.create(block=other, name="Theirs", owner=None, config={})
    placement = page.placements.get()
    placement.default_view = theirs
    with pytest.raises(ValidationError, match="different block"):
        placement.full_clean()


def test_the_view_picker_keeps_your_place(screen, client):
    """Switching a card halfway down a dashboard should not throw you to the
    top: a GET is a fresh navigation however little changed."""
    page, block, ada = screen
    SavedView.objects.create(block=block, name="A", owner=None, config={})
    body = client.get(page.get_absolute_url()).content.decode()
    assert "data-plinta-keep-scroll" in body


# --- the widget data feed ----------------------------------------------------


def url_for(page, placement):
    return f"/pages/{page.pk}/blocks/{placement.pk}/data/"


def test_the_feed_returns_columns_rows_and_paging(screen, client):
    import json

    page, _, _ = screen
    placement = page.placements.get()
    body = json.loads(client.get(url_for(page, placement)).content)
    assert [c["name"] for c in body["columns"]] == ["title"]
    assert {r["title"] for r in body["rows"]} == {"Dune", "Emma"}
    assert body["page"] == {"number": 1, "count": 1, "total": 2, "size": 50}


def test_it_is_placement_scoped_not_block_scoped(screen, client):
    """The placement knows the view, the context filter and the tab, so the
    server reads them from the row rather than trusting the query string."""
    page, block, ada = screen
    second = PageBlock.objects.create(page=page, block=block, order=1)
    first = page.placements.exclude(pk=second.pk).get()

    narrow = SavedView.objects.create(
        block=block, name="None", owner=None, config={"page_size": 1}
    )
    PageBlock.objects.filter(pk=second.pk).update(default_view=narrow)

    import json

    assert json.loads(client.get(url_for(page, first)).content)["page"]["size"] == 50
    assert json.loads(client.get(url_for(page, second)).content)["page"]["size"] == 1


def test_a_context_filter_cannot_be_sent_by_the_client(screen, client):
    """It is read from the placement. v1's endpoint was block-scoped and took
    it as a parameter, so a client could rescope its own card."""
    import json

    page, _, _ = screen
    placement = page.placements.get()
    PageBlock.objects.filter(pk=placement.pk).update(context_filter={"title": "Dune"})
    body = json.loads(client.get(url_for(page, placement)).content)
    assert [r["title"] for r in body["rows"]] == ["Dune"]

    # Asking for the other row does not widen it: the placement's filter is
    # applied whatever arrives.
    body = json.loads(
        client.get(url_for(page, placement), {"context_filter": "{}"}).content
    )
    assert [r["title"] for r in body["rows"]] == ["Dune"]


def test_paging_and_sorting_travel(screen, client):
    import json

    page, _, _ = screen
    placement = page.placements.get()
    body = json.loads(
        client.get(url_for(page, placement), {"size": "1", "sort": "-title"}).content
    )
    assert [r["title"] for r in body["rows"]] == ["Emma"]
    assert body["page"] == {"number": 1, "count": 2, "total": 2, "size": 1}
    assert body["applied"]["sort"] == ["-title"]


def test_a_sort_on_a_column_the_viewer_cannot_see_is_reported_as_dropped(screen, client):
    """The client draws its header from `applied`, never from what it sent —
    or it shows an arrow on a column that is not sorted."""
    import json

    page, _, _ = screen
    placement = page.placements.get()
    body = json.loads(
        client.get(url_for(page, placement), {"sort": "-secret_salary"}).content
    )
    assert body["applied"]["sort"] == []


def test_the_feed_refuses_a_page_the_viewer_may_not_see(screen, client, django_user_model):
    """The gate is the page's own, so reachability over the wire and on the
    screen cannot drift apart."""
    other = django_user_model.objects.create_user("intruder", password="x")  # noqa: S106
    client.force_login(other)
    page, _, _ = screen
    assert client.get(url_for(page, page.placements.get())).status_code == 404


def test_a_placement_on_another_page_is_a_404(screen, client):
    """The URL carries the page, so the gate is the page's own."""
    page, block, ada = screen
    elsewhere = Page.objects.create(name="Other", slug="other", owner=ada)
    stray = PageBlock.objects.create(page=elsewhere, block=block)
    assert client.get(url_for(page, stray)).status_code == 404


def test_anonymous_is_redirected(screen):
    from django.test import Client

    page, _, _ = screen
    response = Client().get(url_for(page, page.placements.get()))
    assert response.status_code == 302

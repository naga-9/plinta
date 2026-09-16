"""A real browser, a real server, and a page with a fetching widget on it.

Why a browser and not jsdom: the bug that prompted this suite was that the
client mounted at `readyState === 'interactive'`, which is when a **deferred**
script runs — so it mounted before the adapters, which are deferred scripts
after it. jsdom does not model deferred execution timing, so a unit runner
would have passed while every fetching component on every page reported that
it had no adapter. The behaviours worth guarding here are the browser's, so
the browser is the only thing that can guard them.
"""
import pytest
from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore

from plinta.blocks.models import Block, SavedView
from plinta.datasources.models import Sorter
from plinta.pages.models import (
    FilterSet,
    Page,
    PageBlock,
    PageFilter,
)
from tests.testapp.models import Book, Region
from tests.support import books_source, build_screen, grant, grant_config_views

#: More than one page of them, so paging is a real request and not a no-op.
BOOKS = 25
PAGE_SIZE = 10


@pytest.fixture
def viewer(ada):
    user = ada
    grant(
        user,
        Book,
        "view_book",
        "change_book",
        "view_book_title",
        "view_book_in_print",
        "change_book_title",
        "view_book_region",
        "change_book_region",
    )
    # The pickers' own models: a related row nobody may see is not one they
    # may be asked to choose.
    grant(user, Region, "view_region")
    grant(user, FilterSet, "add_filterset", "change_filterset", "view_filterset",
          "delete_filterset", "change_filterset_name", "change_filterset_values")
    grant(user, User, "view_user")
    grant(user, Book, "view_book_watchers", "change_book_watchers")
    grant_config_views(user)
    # Saving views, and publishing one: two different acts (§6.1b).
    grant(user, SavedView, "add_savedview", "change_savedview",
          "delete_savedview", "change_savedview_name",
          "change_savedview_config", "change_savedview_is_default")
    return user


@pytest.fixture
def screen(viewer):
    """A page carrying one Tabulator block over 25 books."""
    north = Region.objects.create(name="North")
    south = Region.objects.create(name="South")
    for index in range(BOOKS):
        Book.objects.create(
            title=f"Book {index:02d}",
            owner=viewer,
            region=north if index % 2 == 0 else south,
            in_print=bool(index % 2),
        )

    # A boolean and a relation, both editable: the two that a text box got
    # wrong, so the suite has one of each rather than three strings.
    source = books_source(
        "title", "in_print", "region", "watchers",
        editable=("title", "region", "watchers"),
        filterable=("title", "region", "watchers"),
        options={"title": {"sorter": Sorter.STRING}},
    )
    built = build_screen(
        viewer,
        source,
        component_type="table_tabulator",
        size=(12, 6),
        page_size=PAGE_SIZE,
        header_filters=True,
        editable=True,
        # A pencil per row, opening the record's own form.
        row_form=True,
    )
    PageFilter.objects.create(page=built.page, field_name="in_print", label="In print")
    return built.page, built.block, built.placement


@pytest.fixture
def detail(screen, viewer):
    """A detail page carrying a form over one book.

    A second page rather than a second block on the first: a form is about
    *one* record, and a page that is about one is what supplies it.
    """
    from plinta.pages.models import PageType

    page, block, _ = screen
    source = block.data_source
    detail_page = Page.objects.create(
        name="Book",
        slug="book",
        owner=viewer,
        menu_group=page.menu_group,
        page_type=PageType.DETAIL,
        primary_data_source=source,
    )
    form = Block.objects.create(
        name="book-form",
        component_type="form_plinta",
        data_source=source,
        owner=viewer,
        config={"submit_label": "Save book"},
    )
    PageBlock.objects.create(
        page=detail_page, block=form, column=0, row=0, width=12, height=6
    )
    return detail_page, Book.objects.order_by("title").first()


@pytest.fixture
def signed_in(live_server, context, viewer):
    """A browser context carrying ``viewer``'s session cookie.

    Signing in through the form would test the login page, which is not what
    is under test and would fail every test here for the wrong reason.
    """
    session = SessionStore()
    session[SESSION_KEY] = str(viewer.pk)
    session[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    session[HASH_SESSION_KEY] = viewer.get_session_auth_hash()
    session.create()
    context.add_cookies(
        [
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": session.session_key,
                "url": live_server.url,
            }
        ]
    )
    return context

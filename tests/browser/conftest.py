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
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.backends.db import SessionStore

from plinta.blocks.models import Block, SavedView
from plinta.datasources.models import DataSource, DataSourceField, Sorter
from plinta.pages.models import FilterSet, MenuGroup, MenuSection, Page, PageBlock
from plinta.permissions.fields import sync_model
from tests.testapp.models import Book, Region

#: What a viewer must be able to see for a page to draw at all.
CONFIG_MODELS = (Block, SavedView, Page, FilterSet)

#: More than one page of them, so paging is a real request and not a no-op.
BOOKS = 25
PAGE_SIZE = 10


def grant(user, model, *codenames):
    content_type = ContentType.objects.get_for_model(model)
    for codename in codenames:
        permission, _ = Permission.objects.get_or_create(
            codename=codename, content_type=content_type, defaults={"name": codename}
        )
        user.user_permissions.add(permission)


@pytest.fixture
def viewer(db):
    user = User.objects.create_user(username="ada", password="secret")  # noqa: S106
    grant(user, Book, "view_book", "view_book_title", "view_book_in_print")
    for model in CONFIG_MODELS:
        grant(user, model, f"view_{model._meta.model_name}")
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

    source = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    DataSourceField.objects.create(
        data_source=source,
        field_name="title",
        label="Title",
        sorter=Sorter.STRING,
        filterable=True,
    )
    DataSourceField.objects.create(
        data_source=source, field_name="in_print", label="In print"
    )
    sync_model(Book, {"title": False, "in_print": False})

    section = MenuSection.objects.create(name="Reference")
    group = MenuGroup.objects.create(section=section, name="Catalog")
    page = Page.objects.create(
        name="Catalog", slug="catalog", owner=viewer, menu_group=group
    )
    block = Block.objects.create(
        name="books-table",
        component_type="table_tabulator",
        data_source=source,
        owner=viewer,
        config={"page_size": PAGE_SIZE, "header_filters": True},
    )
    placement = PageBlock.objects.create(
        page=page, block=block, column=0, row=0, width=12, height=6
    )
    return page, block, placement


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

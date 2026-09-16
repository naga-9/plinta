"""What a test builds before it can ask anything: a person, a grant, a model
plinta may draw, a page with a card on it.

Plain functions, and fixtures in the root `conftest.py` composed from them.
Not a factory library: which permissions a test grants is usually what the
test is *about*, and a builder that hid the grant would hide the point. A
file with an unusual shape — two cards, a detail page, a relation filter —
builds it locally, on top of these, where a reader can see it.

Every builder returns a **fresh** row, and `fresh(user)` re-reads a user, so
a permission granted after the first `has_perm` is seen: Django caches a
user's permissions on the instance for its lifetime.
"""
from __future__ import annotations

from typing import NamedTuple

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.blocks.models import Block, SavedView
from plinta.datasources.models import DataSource, DataSourceField
from plinta.pages.models import FilterSet, MenuGroup, MenuSection, Page, PageBlock
from plinta.permissions.fields import sync_model
from tests.testapp.models import Book

#: What a viewer must be able to see for a page to draw at all: the
#: configuration models, each read through its own `view_` permission.
CONFIG_MODELS = (Block, SavedView, Page, FilterSet)


def grant(user, model, *names: str):
    """Give ``user`` permissions on ``model``, and hand them back fresh.

    A name with no underscore is an action — ``"view"`` becomes
    ``view_book`` — and one with an underscore is a codename as it stands
    (``"view_book_title"``, a field permission). The row is made if it does
    not exist, since field permissions are minted by `sync_model` and a test
    may grant one before or after that.
    """
    content_type = ContentType.objects.get_for_model(model)
    for name in names:
        codename = name if "_" in name else f"{name}_{model._meta.model_name}"
        permission, _ = Permission.objects.get_or_create(
            codename=codename, content_type=content_type, defaults={"name": codename}
        )
        user.user_permissions.add(permission)
    return fresh(user)


def grant_config_views(user) -> None:
    """Let ``user`` see every configuration model — what any viewer has."""
    for model in CONFIG_MODELS:
        grant(user, model, "view")


def fresh(user):
    """``user`` read again, with no permission cache."""
    return type(user).objects.get(pk=user.pk)


def person(username: str = "ada") -> User:
    """A signed-up person, with no permissions at all."""
    return User.objects.create_user(username=username, password="secret")  # noqa: S106


def books_source(
    *fields: str, editable: tuple[str, ...] = (), filterable: tuple[str, ...] = ()
) -> DataSource:
    """A DataSource over `Book`, with ``fields`` as columns and their
    permissions minted. ``title`` alone when none are named."""
    names = fields or ("title",)
    source = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    for name in names:
        DataSourceField.objects.create(
            data_source=source,
            field_name=name,
            label=name.split("__")[0].replace("_", " ").capitalize(),
            editable=name in editable,
            filterable=name in filterable,
        )
    sync_model(Book, {name: name in editable for name in names})
    return source


class Screen(NamedTuple):
    """A page with one card on it, and who owns them."""

    page: Page
    block: Block
    placement: PageBlock
    user: User


def build_screen(user, source, *, component_type: str = "table_plinta", **config) -> Screen:
    """The page every screen test starts from: *Catalog*, in the menu under
    *Reference*, with one block over ``source`` filling the left half."""
    section = MenuSection.objects.create(name="Reference")
    group = MenuGroup.objects.create(section=section, name="Catalog")
    page = Page.objects.create(name="Catalog", slug="catalog", owner=user, menu_group=group)
    block = Block.objects.create(
        name="books-table",
        component_type=component_type,
        data_source=source,
        owner=user,
        config=config,
    )
    placement = PageBlock.objects.create(
        page=page, block=block, column=0, row=0, width=6, height=4
    )
    return Screen(page, block, placement, user)

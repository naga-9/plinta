"""A computed column: registered, applied, and sortable in the database."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, DecimalField, IntegerField, Value
from django.db.models.functions import Concat, Upper

from plinta.datasources.annotations import (
    AnnotationError,
    apply,
    get_annotation,
    is_annotation,
)
from plinta.datasources.models import DataSource, DataSourceField
from plinta.datasources.services import get_queryset
from plinta.permissions.fields import sync_model
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db


# --- registering -----------------------------------------------------------


def test_registers_as_a_decorator(annotation_registry):
    @annotation_registry.register_annotation("shouty_title", output_field=None)
    def shouty_title():
        return Upper("title")

    assert is_annotation("shouty_title")
    assert get_annotation("shouty_title").expression is shouty_title


def test_the_output_field_is_kept(annotation_registry):
    """A sorter and a filter widget are chosen from it before any row exists."""
    field = DecimalField()

    @annotation_registry.register_annotation("total", output_field=field)
    def total():
        return Value(1)

    assert get_annotation("total").output_field is field


def test_a_duplicate_is_refused(annotation_registry):
    annotation_registry.register_annotation("total")(lambda: Value(1))
    with pytest.raises(AnnotationError, match="already registered"):
        annotation_registry.register_annotation("total")(lambda: Value(2))


@pytest.mark.parametrize("name", ["Total", "1st", "with-dash", "", "with space"])
def test_an_unusable_name_is_refused(annotation_registry, name):
    with pytest.raises(AnnotationError):
        annotation_registry.register_annotation(name)(lambda: Value(1))


def test_an_unregistered_name_fails_loudly(annotation_registry):
    """A typo fails here, not on every render of the page that names it."""
    with pytest.raises(AnnotationError, match="no annotation named"):
        get_annotation("noneuch")


def test_the_error_lists_what_is_registered(annotation_registry):
    annotation_registry.register_annotation("total")(lambda: Value(1))
    with pytest.raises(AnnotationError, match="registered: total"):
        get_annotation("other")


# --- applying --------------------------------------------------------------


@pytest.fixture
def books(db):
    ada = User.objects.create(username="ada")
    north = Region.objects.create(name="North")
    Book.objects.create(title="Dune", owner=ada, region=north)
    Book.objects.create(title="Emma", owner=ada)
    return ada


def test_an_annotation_reaches_the_rows(annotation_registry, books):
    annotation_registry.register_annotation("shouty")(lambda: Upper("title"))
    rows = apply(Book.objects.all(), ["shouty"])
    assert sorted(r.shouty for r in rows) == ["DUNE", "EMMA"]


def test_a_plain_column_passes_through(annotation_registry, books):
    assert apply(Book.objects.all(), ["title"]).count() == 2


def test_a_computed_column_sorts_in_the_database(annotation_registry, books):
    """What a @property cannot do, being invisible to the ORM."""
    annotation_registry.register_annotation("shouty")(lambda: Upper("title"))
    rows = apply(Book.objects.all(), ["shouty"]).order_by("-shouty")
    assert [r.title for r in rows] == ["Emma", "Dune"]


def test_a_computed_column_filters_in_the_database(annotation_registry, books):
    annotation_registry.register_annotation("shouty")(lambda: Upper("title"))
    rows = apply(Book.objects.all(), ["shouty"]).filter(shouty="DUNE")
    assert rows.count() == 1


def test_an_expression_may_be_anything_django_expresses(annotation_registry, books):
    """Concat, Case, Subquery, Exists, Window — the boundary is where it is
    authored, not what it may contain."""
    annotation_registry.register_annotation("labelled")(
        lambda: Concat("title", Value(" ("), "owner__username", Value(")"))
    )
    rows = apply(Book.objects.all(), ["labelled"]).order_by("title")
    assert [r.labelled for r in rows] == ["Dune (ada)", "Emma (ada)"]


def test_an_aggregate_works(annotation_registry, books):
    annotation_registry.register_annotation(
        "book_count", output_field=IntegerField()
    )(lambda: Count("book", distinct=True))
    rows = apply(Region.objects.all(), ["book_count"])
    assert [r.book_count for r in rows] == [1]


def test_applying_nothing_returns_the_queryset_unchanged(annotation_registry, books):
    qs = Book.objects.all()
    assert apply(qs, ["title", "region__name"]) is qs


# --- through the service ---------------------------------------------------


def test_a_computed_column_arrives_through_get_queryset(annotation_registry, books):
    annotation_registry.register_annotation("shouty")(lambda: Upper("title"))

    ds = DataSource.objects.create(
        name="books", label="Books", content_type=ContentType.objects.get_for_model(Book)
    )
    DataSourceField.objects.create(data_source=ds, field_name="title", label="Title")
    DataSourceField.objects.create(data_source=ds, field_name="shouty", label="Shouty")
    sync_model(Book, {"title": False, "shouty": False})

    ada = User.objects.get(username="ada")
    ct = ContentType.objects.get_for_model(Book)
    for codename in ("view_book", "view_book_title", "view_book_shouty"):
        perm, _ = Permission.objects.get_or_create(
            codename=codename, content_type=ct, defaults={"name": codename}
        )
        ada.user_permissions.add(perm)
    ada = User.objects.get(pk=ada.pk)

    rows = get_queryset(ds, ada)
    assert sorted(r.shouty for r in rows) == ["DUNE", "EMMA"]


def test_a_computed_column_carries_its_own_field_permission(annotation_registry, books):
    """Granted and revoked like any other column's — no new mechanism."""
    annotation_registry.register_annotation("shouty")(lambda: Upper("title"))
    sync_model(Book, {"shouty": False})
    assert Permission.objects.filter(codename="view_book_shouty").exists()


def test_prefetch_derivation_ignores_an_annotation(annotation_registry, books):
    """It is not a relation path, so there is nothing to join."""
    from plinta.datasources.prefetch import derive

    annotation_registry.register_annotation("shouty")(lambda: Upper("title"))
    assert derive(Book, ["shouty"]) == (set(), set())

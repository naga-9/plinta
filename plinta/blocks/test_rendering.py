"""What a block renders, and what a saved view changes about it."""
import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from plinta.blocks.models import Block, SavedView
from plinta.blocks.rendering import (
    EMPTY_SLOT,
    default_view,
    effective_config,
    merge,
    mode_of,
    render_block,
    resolve,
)
from plinta.components.base import Mode
from plinta.datasources.models import DataSource, DataSourceField
from plinta.permissions.fields import sync_model
from tests.testapp.models import Book, Region

pytestmark = pytest.mark.django_db


@pytest.fixture
def block(db):
    ada = User.objects.create(username="ada")
    north = Region.objects.create(name="North")
    Book.objects.create(title="Dune", owner=ada, region=north)
    Book.objects.create(title="Emma", owner=ada, region=north)

    ds = DataSource.objects.create(
        name="books",
        label="Books",
        content_type=ContentType.objects.get_for_model(Book),
    )
    DataSourceField.objects.create(data_source=ds, field_name="title", label="Title")
    DataSourceField.objects.create(
        data_source=ds, field_name="region__name", label="Region"
    )
    sync_model(Book, {"title": False, "region__name": False})

    ct = ContentType.objects.get_for_model(Book)
    for codename in ("view_book", "view_book_title", "view_book_region__name"):
        perm, _ = Permission.objects.get_or_create(
            codename=codename, content_type=ct, defaults={"name": codename}
        )
        ada.user_permissions.add(perm)

    # Both tiers apply to plinta's own models too: seeing a saved view needs
    # the model permission as well as the policy.
    for model, codename in ((Block, "view_block"), (SavedView, "view_savedview")):
        perm, _ = Permission.objects.get_or_create(
            codename=codename,
            content_type=ContentType.objects.get_for_model(model),
            defaults={"name": codename},
        )
        ada.user_permissions.add(perm)

    ada = User.objects.get(pk=ada.pk)
    return Block.objects.create(
        name="books-table", component_type="table", data_source=ds, owner=ada
    ), ada


# --- merging ---------------------------------------------------------------


def test_a_delta_replaces_a_key():
    assert merge({"page_size": 50}, {"page_size": 25}) == {"page_size": 25}


def test_an_omitted_key_is_inherited():
    assert merge({"title": "Books", "page_size": 50}, {"page_size": 25}) == {
        "title": "Books",
        "page_size": 25,
    }


def test_no_delta_leaves_the_block_alone():
    assert merge({"page_size": 50}, None) == {"page_size": 50}


def test_a_list_is_replaced_not_extended():
    """Deep-merging would make "show only these three" impossible to express."""
    assert merge({"columns": ["a", "b", "c"]}, {"columns": ["a"]}) == {"columns": ["a"]}


def test_the_block_config_is_not_mutated():
    base = {"page_size": 50}
    merge(base, {"page_size": 25})
    assert base == {"page_size": 50}


# --- which view applies ----------------------------------------------------


def test_no_saved_view_means_the_blocks_own_config(block):
    b, ada = block
    b.config = {"page_size": 10}
    assert effective_config(b, ada) == {"page_size": 10}


def test_a_viewers_default_view_applies(block):
    b, ada = block
    b.config = {"page_size": 10}
    b.save()
    SavedView.objects.create(
        block=b, name="mine", owner=ada, config={"page_size": 5}, is_default=True
    )
    assert effective_config(b, ada)["page_size"] == 5


def test_a_non_default_view_does_not_apply_by_itself(block):
    b, ada = block
    b.config = {"page_size": 10}
    b.save()
    SavedView.objects.create(block=b, name="mine", owner=ada, config={"page_size": 5})
    assert effective_config(b, ada)["page_size"] == 10


def test_a_named_view_may_be_applied(block):
    b, ada = block
    b.config = {"page_size": 10}
    view = SavedView.objects.create(
        block=b, name="mine", owner=ada, config={"page_size": 5}
    )
    assert effective_config(b, ada, view)["page_size"] == 5


def test_someone_elses_default_is_not_applied(block):
    """Only the viewer's own and the unowned ones are considered."""
    b, ada = block
    b.config = {"page_size": 10}
    b.save()
    bob = User.objects.create(username="bob")
    SavedView.objects.create(
        block=b, name="bob's", owner=bob, config={"page_size": 5}, is_default=True
    )
    assert effective_config(b, ada)["page_size"] == 10


def test_a_public_default_applies_when_the_viewer_has_none(block):
    """How someone who may change views but not the block curates a start."""
    b, ada = block
    b.config = {"page_size": 10}
    b.save()
    SavedView.objects.create(
        block=b, name="shared", owner=None, config={"page_size": 5}, is_default=True
    )
    assert effective_config(b, ada)["page_size"] == 5


def test_the_viewers_own_default_beats_the_public_one(block):
    b, ada = block
    b.config = {"page_size": 10}
    b.save()
    SavedView.objects.create(
        block=b, name="shared", owner=None, config={"page_size": 5}, is_default=True
    )
    SavedView.objects.create(
        block=b, name="mine", owner=ada, config={"page_size": 7}, is_default=True
    )
    assert effective_config(b, ada)["page_size"] == 7


def test_a_public_view_not_marked_default_is_not_applied(block):
    """Nothing is picked by accident: only a mark someone made deliberately."""
    b, ada = block
    b.config = {"page_size": 10}
    b.save()
    SavedView.objects.create(block=b, name="aaa", owner=None, config={"page_size": 5})
    assert effective_config(b, ada)["page_size"] == 10


def test_without_the_model_permission_no_view_applies(block):
    """The lookup goes through `allowed`, so both permission tiers gate it."""
    b, ada = block
    b.config = {"page_size": 10}
    b.save()
    SavedView.objects.create(
        block=b, name="shared", owner=None, config={"page_size": 5}, is_default=True
    )
    ada.user_permissions.remove(Permission.objects.get(codename="view_savedview"))
    ada = User.objects.get(pk=ada.pk)
    assert effective_config(b, ada)["page_size"] == 10


def test_an_anonymous_viewer_has_no_default(block):
    b, _ = block
    assert default_view(b, None) is None


# --- resolving -------------------------------------------------------------


def test_resolve_validates_against_the_components_schema(block):
    b, ada = block
    b.config = {"page_size": 25}
    assert resolve(b, ada).page_size == 25


def test_resolve_returns_none_for_an_uninstalled_component(block):
    b, ada = block
    b.component_type = "heatmap"
    assert resolve(b, ada) is None


# --- the mode --------------------------------------------------------------


def test_a_block_inherits_the_components_mode(block):
    b, _ = block
    assert mode_of(b) is Mode.INLINE


def test_a_block_may_override_the_mode(block):
    b, _ = block
    b.mode = "fetch"
    assert mode_of(b) is Mode.FETCH


def test_an_uninstalled_component_has_no_mode(block):
    b, _ = block
    b.component_type = "gone"
    assert mode_of(b) is None


# --- rendering -------------------------------------------------------------


def test_it_draws_the_component(block):
    b, ada = block
    out = render_block(b, ada)
    assert "<td>Dune</td>" in out


def test_an_uninstalled_component_is_an_empty_slot(block):
    """A page must not break because a component's package was removed."""
    b, ada = block
    b.component_type = "heatmap"
    b.save()
    assert render_block(b, ada) == EMPTY_SLOT


def test_a_block_the_viewer_may_not_see_is_an_empty_slot(block):
    b, ada = block
    bob = User.objects.create(username="bob")
    assert render_block(b, bob) == EMPTY_SLOT


def test_an_inactive_block_is_an_empty_slot(block):
    b, ada = block
    b.is_active = False
    b.save()
    assert render_block(b, ada) == EMPTY_SLOT


def test_a_saved_view_reaches_the_component(block):
    b, ada = block
    view = SavedView.objects.create(
        block=b, name="titles", owner=ada, config={"columns": ["title"]}
    )
    out = render_block(b, ada, view=view)
    assert "<th>Title</th>" in out
    assert "<th>Region</th>" not in out


def test_a_saved_view_cannot_widen_what_the_viewer_may_see(block):
    """Personalisation is not a permission bypass."""
    b, ada = block
    ada.user_permissions.remove(Permission.objects.get(codename="view_book_title"))
    ada = User.objects.get(pk=ada.pk)
    view = SavedView.objects.create(
        block=b, name="titles", owner=ada, config={"columns": ["title"]}
    )
    out = render_block(b, ada, view=view)
    assert "<th>Title</th>" not in out
    assert "Dune" not in out


def test_a_block_that_cannot_be_drawn_raises_a_block_error(block, settings):
    """Not the component's own exception: a caller drawing eight blocks needs
    to know which one failed and carry on, not to handle every kind of failure
    a component can have."""
    from plinta.blocks.rendering import BlockRenderError

    settings.DEBUG = False
    b, ada = block
    b.config = {"page_sise": 10}
    b.save()
    with pytest.raises(BlockRenderError) as exc:
        render_block(b, ada)
    assert exc.value.block_name == "books-table"


def test_in_debug_the_original_error_is_raised(block, settings):
    """A developer wants the traceback, not a tidy card."""
    from plinta.components.base import ConfigError

    settings.DEBUG = True
    b, ada = block
    b.config = {"page_sise": 10}
    b.save()
    with pytest.raises(ConfigError):
        render_block(b, ada)


def test_a_failure_is_logged_with_its_traceback(block, settings, caplog):
    from plinta.blocks.rendering import BlockRenderError

    settings.DEBUG = False
    b, ada = block
    b.config = {"page_sise": 10}
    b.save()
    with pytest.raises(BlockRenderError):
        render_block(b, ada)
    assert "books-table" in caplog.text

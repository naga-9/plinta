"""Everything `catalog` plugs into plinta with.

One module rather than eight, because a reader wanting to know what a consumer
may do should be able to read it in one sitting. A larger app would split it.

Every import below is from plinta's published surface (§18). If this file ever
needs a private path, that is a gap in the API rather than a licence to reach
inside — which is the whole reason this app exists (§1.4).
"""
from decimal import Decimal
from types import SimpleNamespace

from django.db.models import DecimalField, F
from django.utils.html import format_html, format_html_join
from pydantic import Field as PydanticField

from plinta.blocks.capabilities import register_capability
from plinta.components.base import Component, ComponentConfig, Mode
from plinta.components.registry import register_component
from plinta.datasources.annotations import register_annotation
from plinta.forms.layouts import register_config_layout
from plinta.datasources.modifiers import register_queryset_modifier
from plinta.events import signals
from plinta.permissions.actions import register_action
from plinta.permissions.policies import PermissionPolicy, register_policy
from plinta.permissions.rules import (
    FieldInUserSet,
    HasPerm,
    InstancePerm,
    Owner,
    Public,
)
from plinta.renderers.fields import register_field_renderer
from plinta.renderers.format import format_number
from plinta.shell.links import register_shell_link
from plinta.utils.placeholders import register_placeholder
from plinta.utils.styles import classes

from catalog.models import (
    Book,
    OrderStatus,
    Promotion,
    PurchaseOrder,
    PurchaseOrderLine,
    Sale,
    StockMovement,
    Store,
)

# --- policies: which rows, for whom ----------------------------------------


def stores_of(user):
    """The stores this user manages. The demo's whole tenancy."""
    return user.managed_stores.all()


class SalePolicy(PermissionPolicy):
    """A manager sees their own stores' sales; head office sees every one.

    Structural scoping with no `contrib.organization` in sight: core supplies
    the shape, the consumer supplies what a store is and who manages one.

    Reading is wider than writing on purpose. Head office is defined by
    `change_store` — whoever may edit the branches may read across them — but
    that grants no power to record or delete a sale at a shop they do not run.
    """

    view = HasPerm("catalog.change_store") | FieldInUserSet("store", user_set=stores_of)
    change = FieldInUserSet("store", user_set=stores_of)
    delete = FieldInUserSet("store", user_set=stores_of)


class StorePolicy(PermissionPolicy):
    """A manager sees the stores they manage, and head office sees all.

    Needed because a filter's options are only as narrow as the policy on the
    model they come from. `SalePolicy` scopes sales; without this, a Store
    multi-select would offer every branch by name to somebody who may not see
    a single row from most of them — the rows protected and the list not.
    """

    view = HasPerm("catalog.change_store") | FieldInUserSet("pk", user_set=stores_of)


class PurchaseOrderPolicy(PermissionPolicy):
    view = FieldInUserSet("store", user_set=stores_of)
    # Placing an order is a manager's, but cancelling one is the head office's.
    change = FieldInUserSet("store", user_set=stores_of)
    delete = HasPerm("catalog.delete_purchaseorder") & FieldInUserSet(
        "store", user_set=stores_of
    )


class PurchaseOrderLinePolicy(PermissionPolicy):
    """A line is scoped by the order it belongs to.

    Added because `plinta.datasources.W001` reported it: the order was scoped
    and the line was not, so every manager could read every store's lines
    through the second block on the same page. Scoping a parent is not scoping
    its children, and the check is what says so out loud.
    """

    view = FieldInUserSet("order__store", user_set=stores_of)
    change = FieldInUserSet("order__store", user_set=stores_of)
    delete = FieldInUserSet("order__store", user_set=stores_of)


class PromotionPolicy(PermissionPolicy):
    """Owned, shareable, and public when it has no owner."""

    view = Owner() | Public() | InstancePerm("catalog", "promotion", "view")
    change = Owner() | InstancePerm("catalog", "promotion", "change")
    delete = Owner()


# `Book` deliberately has no policy. The catalogue is shared, so the model
# permission decides alone — the case §5.3 calls legitimate, and the reason
# plinta.datasources.W001 is a warning rather than an error.


# --- computed columns ------------------------------------------------------


@register_annotation("sale_total", output_field=DecimalField(max_digits=12,
                                                             decimal_places=2))
def sale_total():
    """What a sale came to. Sorts and filters in the database, which a
    ``@property`` on `Sale` could not."""
    return F("quantity") * F("unit_price")


@register_annotation("line_total", output_field=DecimalField(max_digits=12,
                                                             decimal_places=2))
def line_total():
    return F("quantity") * F("unit_cost")


# --- queryset modifiers ----------------------------------------------------


@register_queryset_modifier("open_orders")
def open_orders(queryset, user, **kwargs):
    """Orders still outstanding. Narrows; never widens."""
    return queryset.exclude(status__in=[OrderStatus.RECEIVED, OrderStatus.CANCELLED])


@register_queryset_modifier("in_print_only")
def in_print_only(queryset, user, **kwargs):
    return queryset.filter(in_print=True)


# --- placeholders ----------------------------------------------------------


@register_placeholder("my_stores")
def my_stores(context):
    """``__MY_STORES__`` — the ids of the stores this viewer manages.

    Resolved per request, so one block configuration shows each manager their
    own shops.
    """
    user = context.user
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    return list(stores_of(user).values_list("pk", flat=True))


# --- field renderers -------------------------------------------------------


@register_field_renderer("stock_badge")
def stock_badge(value, *, obj, field, user):
    """In print, or not. Markup, so it goes through `format_html`.

    A status is the one place colour carries meaning rather than decoration,
    so the two states use different chips. Rendered identically they read as a
    label nobody needs to scan.
    """
    cls = classes()
    return format_html(
        '<span class="{} {}">{}</span>',
        cls["chip"],
        cls["chip_success"] if obj.in_print else cls["chip_neutral"],
        "In print" if obj.in_print else "Out of print",
    )


@register_field_renderer("store_link", select_related=["store", "store__region"])
def store_link(value, *, obj, field, user):
    """The store, with its region.

    Declares the joins it reads: the column is `sold_on` on some screens, so
    derivation cannot see that this renderer reaches `store__region` (§7.8).
    """
    return format_html("{} <span class='pl-muted'>({})</span>",
                       obj.store.name, obj.store.region.code)


@register_field_renderer("note_count", prefetch_related=["notes"])
def note_count(value, *, obj, field, user):
    notes = list(obj.notes.all())
    if not notes:
        return format_html("<span class='pl-muted'>—</span>")
    chip = f"{classes()['chip']} {classes()['chip_info']}"
    return format_html_join(" ", '<span class="' + chip + '">{}</span>',
                            ((f"{len(notes)} notes",),))


# --- actions ---------------------------------------------------------------

# `export_*` is minted for every registered DataSource. Nothing exports yet —
# contrib.export is not installed — but the permission exists, so a console can
# grant it before the package arrives.
register_action("export", "export")


# --- a component, from outside core ----------------------------------------


class StatConfig(ComponentConfig):
    """One number, and what to call it."""

    label: str = ""
    #: A column to total. Blank counts the rows instead.
    total_field: str = PydanticField(
        default="",
        title="Field to total",
        description="Summed across the rows. Leave empty to count them.",
        json_schema_extra={"widget": "column", "kinds": ["number"]},
    )
    prefix: str = ""
    suffix: str = ""
    #: How many places the figure shows. A sum over an annotation carries
    #: whatever precision the arithmetic produced — £253.42000000000000 is
    #: arithmetic showing through, not a number anybody wrote.
    decimals: int | None = None


# Its settings, arranged. Core draws the controls; this says where they go —
# the split a component owns (§12.3a). Without it they stack, which is fine
# for a table and thin for anything with two kinds of setting.
register_config_layout(StatConfig, "catalog/stat_settings.html")


@register_component("stat_catalog", label="Statistic")
class StatComponent(Component):
    """A single figure. The smallest thing that proves the door is real.

    Inline: one number is a finished blob, so there is nothing to fetch.
    """

    config_schema = StatConfig
    mode = Mode.INLINE
    supported_modes = frozenset({Mode.INLINE})

    def render(self, config, user, **context) -> str:
        rows, _ = self.get_data(
            config,
            user,
            datasource=context["datasource"],
            narrow=context.get("narrow"),
        )
        if config.total_field:
            from django.db.models import Sum

            total = rows.aggregate(total=Sum(config.total_field))["total"] or Decimal(0)
        else:
            total = rows.count()
        return format_html(
            '<div class="pl-stat"><div class="pl-stat__value">{}{}{}</div>'
            '<div class="pl-stat__label">{}</div></div>',
            config.prefix,
            # Core's own formatter, reached the way any consumer reaches it:
            # a component that formats its own numbers is a second answer to a
            # question `renderers` already answers, and drifts from the table
            # beside it.
            format_number(total, SimpleNamespace(decimals=config.decimals,
                                                 thousands_separator=True)),
            config.suffix,
            config.label,
        )


# --- a capability ----------------------------------------------------------


def annotated_models():
    """Every model declaring a GenericRelation to our note. Computed once."""
    from django.apps import apps
    from django.contrib.contenttypes.fields import GenericRelation

    from catalog.models import CatalogNote

    return {
        model
        for model in apps.get_models()
        for f in model._meta.get_fields()
        if isinstance(f, GenericRelation) and f.related_model is CatalogNote
    }


register_capability(
    "catalog_notes",
    "Notes",
    applies_to=lambda obj, user=None, **kw: getattr(obj, "pk", None) is not None,
    supports=lambda model, state=None, **kw: model in (state or set()),
    prepare=annotated_models,
    template="catalog/notes_section.html",
    order=200,
)


# --- an event listener -----------------------------------------------------


def record_stock_movement(sender, obj, mode, changes, actor=None, source="", **kwargs):
    """Turn a sale into a stock movement.

    A subscriber, not a stage: `blocks` has no idea this app exists, and
    removing `catalog` removes the behaviour with it (§4.10).
    """
    if not isinstance(obj, Sale):
        return
    before, after = changes.get("quantity", (0, obj.quantity))
    moved = (after or 0) - (before or 0)
    if moved:
        StockMovement.objects.create(
            book=obj.book, change=-moved, reason=f"sale {mode}"
        )


def connect_listeners():
    """Called from `AppConfig.ready()`, where a receiver belongs."""
    signals.object_written.connect(
        record_stock_movement, dispatch_uid="catalog.stock_movement"
    )


# --- a screen that is not a page -------------------------------------------


def register_links():
    register_shell_link(
        "catalogue_admin",
        "Catalogue admin",
        url_name="catalogue_admin",
        permission="catalog.change_book",
        icon="plinta:settings",
        # Consumer screens 0-99, contrib 100-899, administration 900+ — `order`
        # is the only coordination between apps that never see each other.
        section="Bookshop",
        group="Manage",
        order=50,
    )


__all__ = [
    "PromotionPolicy",
    "PurchaseOrderPolicy",
    "SalePolicy",
    "StatComponent",
    "Store",
    "connect_listeners",
    "register_links",
    "stores_of",
]


def register_policies():
    """Bind the policies to their models, from `AppConfig.ready()`."""
    register_policy(Sale, SalePolicy)
    register_policy(Store, StorePolicy)
    register_policy(PurchaseOrder, PurchaseOrderPolicy)
    register_policy(PurchaseOrderLine, PurchaseOrderLinePolicy)
    register_policy(Promotion, PromotionPolicy)
    # Book: none, deliberately.
    assert Book is not None

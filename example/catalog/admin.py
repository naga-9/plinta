"""The bookshop's models in Django's admin.

Not how the demo is meant to be read — every screen worth looking at is a
plinta `Page`, and the point of the project is that those screens need no
admin. This is here so `root` can create a row or fix one while trying
something out, without a shell.

Nothing below is permission-aware: the admin answers to `is_staff` and the
model permission, and knows nothing about policies. A store manager's scoping
is visible on the plinta screens, never here.
"""
from django.contrib import admin

from catalog.models import (
    Book,
    CatalogNote,
    Promotion,
    PurchaseOrder,
    PurchaseOrderLine,
    Region,
    Sale,
    StockMovement,
    Store,
)


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "region", "opened_on")
    list_filter = ("region",)
    search_fields = ("name",)
    # Who manages a store is the demo's whole tenancy — `SalePolicy` scopes on
    # it — so it is worth editing here and watching a plinta screen change.
    filter_horizontal = ("managers",)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "price", "published_on", "in_print")
    list_filter = ("in_print",)
    search_fields = ("title", "author", "isbn")
    date_hierarchy = "published_on"


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("book", "store", "sold_on", "quantity", "unit_price")
    list_filter = ("store", "sold_on")
    search_fields = ("book__title",)
    date_hierarchy = "sold_on"
    autocomplete_fields = ("book", "store")


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 0
    autocomplete_fields = ("book",)


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("supplier", "store", "ordered_on", "expected_on", "status")
    list_filter = ("status", "store")
    search_fields = ("supplier",)
    date_hierarchy = "ordered_on"
    autocomplete_fields = ("store",)
    inlines = [PurchaseOrderLineInline]


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ("name", "book", "starts_on", "ends_on", "discount_pct", "owner")
    list_filter = ("starts_on",)
    search_fields = ("name",)
    autocomplete_fields = ("book", "owner")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("book", "change", "reason", "at")
    list_filter = ("reason",)
    search_fields = ("book__title",)
    readonly_fields = ("at",)


@admin.register(CatalogNote)
class CatalogNoteAdmin(admin.ModelAdmin):
    list_display = ("author", "written_at", "content_type", "object_id")
    list_filter = ("content_type",)
    readonly_fields = ("written_at",)

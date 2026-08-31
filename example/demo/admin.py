"""plinta's configuration models in the demo's admin.

**A stopgap, and the demo's rather than plinta's.** Core ships no `admin.py`
anywhere: §12's authoring screens — the Data Sources screen, the Blocks
catalogue, the block inspector, the page composer — are how this configuration
is meant to be edited, and they are not built yet. Until they are, this is
somewhere to look at a `Page` and see that a screen really is a row.

It lives in the demo project, not in plinta, so it disappears when §12 lands
rather than becoming a second way to do the same thing — and `demo` is an
installed app so that registering from `admin.py` is the same door `catalog`
goes through, rather than an import smuggled into the URLconf.

Two things it cannot do, by construction:

- **Arrange a page.** `PageBlock` carries row, column, width and height, which
  are meant to be dragged rather than typed. The composer is the answer.
- **Validate a block's config.** `config` is a JSON field whose shape belongs
  to the component; the block inspector derives a real form from the schema,
  and this shows the raw JSON.
"""
from django.contrib import admin

from plinta.blocks.models import Block, SavedView
from plinta.datasources.models import DataSource, DataSourceField
from plinta.pages.models import (
    FilterSet,
    MenuGroup,
    MenuSection,
    Page,
    PageBlock,
    PageFilter,
)


class DataSourceFieldInline(admin.TabularInline):
    model = DataSourceField
    extra = 0
    # A column exists because it is listed here, and saving one mints that
    # column's permissions — adding a row is a permission change.
    fields = ("field_name", "label", "order", "visible", "format", "renderer")


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "label", "content_type")
    search_fields = ("name", "label")
    inlines = [DataSourceFieldInline]


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("name", "component_type", "data_source", "mode")
    list_filter = ("component_type",)
    search_fields = ("name",)


@admin.register(SavedView)
class SavedViewAdmin(admin.ModelAdmin):
    list_display = ("name", "block", "owner", "is_default")
    list_filter = ("is_default",)
    search_fields = ("name",)


class PageBlockInline(admin.TabularInline):
    model = PageBlock
    extra = 0
    fields = ("block", "row", "column", "width", "height")


class PageFilterInline(admin.TabularInline):
    model = PageFilter
    extra = 0


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "page_type", "menu_group", "is_active")
    list_filter = ("page_type", "is_active", "menu_group")
    search_fields = ("name", "slug")
    inlines = [PageBlockInline, PageFilterInline]


@admin.register(FilterSet)
class FilterSetAdmin(admin.ModelAdmin):
    list_display = ("name", "page", "owner", "is_default")
    list_filter = ("is_default",)


admin.site.register(MenuSection)
admin.site.register(MenuGroup)

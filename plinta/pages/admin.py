"""Pages, their composition and their menu, in Django's admin.

The page composer (§12.4) is where a page is arranged, because row, column,
width and height are meant to be dragged rather than typed. Typing them here
works and is occasionally the fastest way to fix one.
"""
from django.contrib import admin

from plinta.pages.models import (
    FilterSet,
    MenuGroup,
    MenuSection,
    Page,
    PageBlock,
    PageFilter,
    PageFilterPreference,
)


class PageBlockInline(admin.TabularInline):
    """Which blocks a page carries, and where each sits on the grid."""

    model = PageBlock
    extra = 0
    fields = ("block", "row", "column", "width", "height")
    ordering = ("row", "column")
    autocomplete_fields = ("block",)


class PageFilterInline(admin.TabularInline):
    """The controls the page exposes above its blocks."""

    model = PageFilter
    extra = 0
    ordering = ("order",)


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "page_type", "menu_group", "is_active",
                    "show_in_menu")
    list_filter = ("page_type", "is_active", "show_in_menu", "menu_group")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [PageBlockInline, PageFilterInline]


@admin.register(MenuSection)
class MenuSectionAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    ordering = ("order", "name")


@admin.register(MenuGroup)
class MenuGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "section", "order")
    list_filter = ("section",)
    ordering = ("section", "order")


@admin.register(FilterSet)
class FilterSetAdmin(admin.ModelAdmin):
    """A named set of filter values, owned by a viewer or shared.

    A row with no owner is the shared one. `values` is JSON because the
    controls a page exposes are configuration, not fields.
    """

    list_display = ("name", "page", "owner", "is_default")
    list_filter = ("is_default", "page")
    search_fields = ("name",)
    autocomplete_fields = ("owner",)


@admin.register(PageFilterPreference)
class PageFilterPreferenceAdmin(admin.ModelAdmin):
    """What a viewer last had a page's controls set to. Remembered, not chosen."""

    list_display = ("page", "owner")
    list_filter = ("page",)
    autocomplete_fields = ("owner",)

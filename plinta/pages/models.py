"""A Page composes blocks, gives them a filter bar, and sits in the menu.

`FilterSet` and `PageFilterPreference` live here for the same reason `SavedView`
lives in `blocks`: each sits with the thing it is a delta over.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models


class PageType(models.TextChoices):
    DASHBOARD = "dashboard", "Dashboard"
    DETAIL = "detail", "Detail"
    CUSTOM_TEMPLATE = "custom-template", "Custom template"


class MenuSection(models.Model):
    """The top level of the navigation.

    Visibility follows the pages inside it, which are already permission
    filtered, so it carries no flag of its own.
    """

    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name


class MenuGroup(models.Model):
    """A group of pages within a section."""

    section = models.ForeignKey(
        MenuSection, on_delete=models.CASCADE, related_name="groups"
    )
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["section", "name"], name="unique_group_per_section"
            )
        ]

    def __str__(self) -> str:
        return f"{self.section.name} / {self.name}"


class Page(models.Model):
    """A screen: blocks, a filter bar, and a place in the menu.

    Addressed by id. The slug is decorative and unique only per owner, so
    everyone may have a page called ``my-dashboard`` and a shared link still
    resolves to the page that was shared.
    """

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True, default="")
    page_type = models.CharField(
        max_length=20, choices=PageType, default=PageType.DASHBOARD
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="pages",
        help_text="Null is public.",
    )
    is_active = models.BooleanField(default=True)

    # --- menu placement ---
    show_in_menu = models.BooleanField(default=True)
    menu_group = models.ForeignKey(
        MenuGroup,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pages",
    )
    menu_order = models.PositiveIntegerField(default=0)
    menu_icon = models.CharField(max_length=50, blank=True, default="")

    # --- per page type ---
    template_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="How a custom-template page resolves. A path plinta or a "
        "consumer ships, not authored content.",
    )
    primary_data_source = models.ForeignKey(
        "plinta_datasources.DataSource",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="detail_pages",
        help_text="The model a detail page shows.",
    )
    context_param = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="The URL parameter a detail page binds its record to.",
    )
    tabs = models.JSONField(
        default=list,
        blank=True,
        help_text="Nav tabs above the blocks. The active tab reaches blocks as "
        "a request parameter.",
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Page-level settings for a contrib package, under its own "
        "key. Core never inspects them.",
    )

    class Meta:
        ordering = ["menu_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "slug"], name="unique_page_slug_per_owner"
            ),
            # NULL does not compare equal in SQL, so the constraint above lets
            # two public pages share a slug. This one covers them.
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(owner__isnull=True),
                name="unique_public_page_slug",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        """``/pages/<id>-<slug>/``. The id resolves it; the slug is readable."""
        return f"/pages/{self.pk}-{self.slug}/"


class PageBlock(models.Model):
    """A block placed on a page at a grid position.

    Travels with its page and is never independently shareable. The same block
    may appear on several pages at different sizes.
    """

    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="placements")
    block = models.ForeignKey(
        "plinta_blocks.Block", on_delete=models.CASCADE, related_name="placements"
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Shown instead of the block's own name. Blank uses it.",
    )
    # Position on a twelve-column grid, in cells. Both coordinates are stored
    # because a block stays exactly where it was dropped — there is no gravity
    # pulling it up, so a row cannot be derived from the order.
    column = models.PositiveSmallIntegerField(default=0)
    row = models.PositiveSmallIntegerField(default=0)
    width = models.PositiveSmallIntegerField(default=6)
    height = models.PositiveSmallIntegerField(
        default=4, help_text="In grid cells, not pixels."
    )
    order = models.PositiveIntegerField(
        default=0, help_text="Tie-breaker, and the order on a page with no grid."
    )
    is_visible = models.BooleanField(default=True)
    context_filter = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extra filter values for this placement only. Placeholders "
        "resolve.",
    )
    tab = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Which tab shows this placement. Blank shows it on all.",
    )

    class Meta:
        ordering = ["order", "row", "column"]

    def __str__(self) -> str:
        return f"{self.page.name}: {self.block.name}"


#: The names core registers. Kept as constants because the code refers to
#: them; the set of *valid* names is the registry, not this (`pages.widgets`).
class Widget:
    """Core's own filter widgets, by name."""

    INPUT = "input"
    SELECT = "select"
    MULTISELECT = "multiselect"
    DATERANGE = "daterange"
    BOOLEAN = "boolean"


class Lookup(models.TextChoices):
    EXACT = "exact", "Exact"
    IN = "in", "One of"
    RANGE = "range", "Between"
    ICONTAINS = "icontains", "Contains"


class PageFilter(models.Model):
    """One control on a page's filter bar.

    Page furniture: always visible, no permissions of its own, and driven by
    the viewer — which is what separates it from a block's `base_filter`.
    """

    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="filters")
    field_name = models.CharField(
        max_length=100, help_text="Field path the control filters on."
    )
    label = models.CharField(max_length=200)
    widget = models.CharField(
        max_length=50,
        default="input",
        help_text="A registered filter widget. An unregistered one draws as "
        "a text input.",
    )
    lookup = models.CharField(max_length=20, choices=Lookup, default=Lookup.EXACT)
    order = models.PositiveIntegerField(default=0)
    #: Where a select's options come from. A page's blocks may read different
    #: models, so which one this control names is stated rather than guessed —
    #: "the first block that has the field" is the kind of implicit rule that
    #: bites once a page has two.
    data_source = models.ForeignKey(
        "plinta_datasources.DataSource",
        on_delete=models.SET_NULL,
        related_name="page_filters",
        null=True,
        blank=True,
        help_text="Needed only by a widget that offers options to choose from.",
    )
    default_value = models.JSONField(
        default=None,
        null=True,
        blank=True,
        help_text="Applied when the viewer has set nothing. Placeholders resolve.",
    )

    class Meta:
        ordering = ["order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["page", "field_name"], name="unique_filter_per_page"
            )
        ]

    def __str__(self) -> str:
        return f"{self.page.name}: {self.label}"


class FilterSet(models.Model):
    """A named set of filter values a viewer saved on a page.

    The same delta-over-a-base shape a `SavedView` has over a block, which is
    why it lives with the page rather than in a personalisation app.
    """

    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="filter_sets")
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="filter_sets",
        help_text="Null is public.",
    )
    values = models.JSONField(
        default=dict,
        blank=True,
        help_text="Filter values. Placeholders are stored as written and "
        "resolve at query time.",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Applied when a viewer has set no filters. Their own default "
        "wins over a public one.",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["page", "owner", "name"],
                name="unique_filterset_name_per_page_and_owner",
            ),
            models.UniqueConstraint(
                fields=["page", "name"],
                condition=models.Q(owner__isnull=True),
                name="unique_public_filterset_name_per_page",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.page.name}: {self.name}"


class PageFilterPreference(models.Model):
    """What one viewer last had the filter bar set to.

    Remembered state rather than a saved set: unnamed, one per viewer per page,
    and overwritten as they filter.
    """

    page = models.ForeignKey(
        Page, on_delete=models.CASCADE, related_name="filter_preferences"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="filter_preferences",
    )
    values = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["page", "owner"], name="unique_preference_per_page_and_owner"
            )
        ]

    def __str__(self) -> str:
        return f"{self.page.name}: {self.owner}"

"""A Block is a saved component configuration bound to a DataSource.

A `SavedView` is a delta over one, which is why it lives here: each sits with
the thing it is a delta over.
"""
from __future__ import annotations

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

NAME_VALIDATOR = RegexValidator(
    regex=r"^[a-z][a-z0-9_-]*$",
    message="Must start with a lowercase letter and contain only lowercase "
    "letters, numbers, hyphens and underscores.",
)


class Mode(models.TextChoices):
    """Overrides the component's default (§7.3). Blank inherits it."""

    INHERIT = "", "Component default"
    INLINE = "inline", "Inline"
    FETCH = "fetch", "Fetch"


class Block(models.Model):
    """One widget: a component, a DataSource, and the config binding them."""

    name = models.SlugField(max_length=100, validators=[NAME_VALIDATOR])
    component_type = models.CharField(
        max_length=50,
        help_text="A registered component. An unregistered one renders an empty slot.",
    )
    data_source = models.ForeignKey(
        "plinta_datasources.DataSource",
        on_delete=models.PROTECT,
        related_name="blocks",
        help_text="A block cannot exist without the model it reads.",
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Checked against the component's schema by full_clean.",
    )
    base_filter = models.JSONField(
        default=dict,
        blank=True,
        help_text="Locked filter values, chosen by whoever built the screen "
        "rather than by the viewer.",
    )
    queryset_modifier = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="A registered queryset modifier's name. Not an import path.",
    )
    mode = models.CharField(max_length=10, choices=Mode, blank=True, default="")

    description = models.TextField(blank=True, default="")
    icon = models.CharField(max_length=50, blank=True, default="")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="blocks",
        help_text="Null is public.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="unique_block_name_per_owner",
            ),
            # NULL does not compare equal in SQL, so the constraint above lets
            # two public blocks share a name. This one covers them.
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(owner__isnull=True),
                name="unique_public_block_name",
            ),
        ]

    def clean(self) -> None:
        """Check ``config`` against the component's schema.

        Raises a `ValidationError` on a key the component does not declare,
        which is what makes ``extra='forbid'`` a save-time answer rather than a
        render-time surprise. A component that is not installed cannot say, so
        the config is left as written — the same reason an uninstalled
        component renders an empty slot instead of failing.
        """
        from django.core.exceptions import ValidationError

        from plinta.components.base import ConfigError
        from plinta.components.registry import find

        component = find(self.component_type)
        if component is None:
            return
        try:
            component.validate(self.config)
        except ConfigError as exc:
            raise ValidationError({"config": str(exc)}) from exc

    def __str__(self) -> str:
        return self.name


class SavedView(models.Model):
    """One viewer's delta over a block's config.

    The block is a **foreign key**, never its name: a name is unique only per
    owner, and renaming a block would otherwise orphan every view on it
    silently.
    """

    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name="saved_views")
    name = models.CharField(max_length=100)
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="The delta. Merged over the block's config when rendering.",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="saved_views",
        help_text="Null is public.",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Applied when a viewer has chosen no view. Their own default "
        "wins over a public one.",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["block", "owner", "name"],
                name="unique_view_name_per_block_and_owner",
            ),
            # NULL does not compare equal in SQL, so the constraint above lets
            # two public views share a name. This one covers them.
            models.UniqueConstraint(
                fields=["block", "name"],
                condition=models.Q(owner__isnull=True),
                name="unique_public_view_name_per_block",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.block.name}: {self.name}"

"""A bookshop chain, as plain Django models.

Nothing here inherits from plinta, and nothing here imports it. A model that
plinta shows is an ordinary model — that promise is what this app exists to
keep honest (§1.4).
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Region(models.Model):
    name = models.CharField(max_length=60, unique=True)
    code = models.CharField(max_length=8, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Store(models.Model):
    """A shop. Its managers are the demo's tenancy.

    `SalePolicy` scopes rows through this relation, which is the whole of what
    `contrib.organization` would otherwise supply: core's `FieldInUserSet`
    knows a field name and how to derive a set from a user, and nothing else.
    """

    name = models.CharField(max_length=80)
    region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name="stores")
    opened_on = models.DateField()
    managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="managed_stores"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Book(models.Model):
    """The catalogue. Deliberately has no policy: it is shared, and every
    holder of `view_book` sees all of it (§5.3)."""

    title = models.CharField(max_length=200)
    author = models.CharField(max_length=120)
    isbn = models.CharField(max_length=17, unique=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    published_on = models.DateField()
    in_print = models.BooleanField(default=True)
    notes = GenericRelation("catalog.CatalogNote")

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class Sale(models.Model):
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="sales")
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="sales")
    sold_on = models.DateField()
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        ordering = ["-sold_on", "-pk"]

    def __str__(self) -> str:
        return f"{self.book} × {self.quantity}"


class OrderStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PLACED = "placed", "Placed"
    RECEIVED = "received", "Received"
    CANCELLED = "cancelled", "Cancelled"


class PurchaseOrder(models.Model):
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="orders")
    supplier = models.CharField(max_length=120)
    ordered_on = models.DateField()
    expected_on = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=12, choices=OrderStatus, default=OrderStatus.DRAFT
    )

    class Meta:
        ordering = ["-ordered_on", "-pk"]

    def __str__(self) -> str:
        return f"{self.supplier} — {self.ordered_on}"


class PurchaseOrderLine(models.Model):
    order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="lines"
    )
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="order_lines")
    quantity = models.PositiveIntegerField(default=1)
    unit_cost = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        ordering = ["pk"]

    def __str__(self) -> str:
        return f"{self.book} × {self.quantity}"


class Promotion(models.Model):
    """A buyer's campaign. Owned, shareable, and the demo's `Owner` case."""

    name = models.CharField(max_length=120)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="promotions")
    starts_on = models.DateField()
    ends_on = models.DateField()
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="promotions",
        help_text="Null is public.",
    )

    class Meta:
        ordering = ["-starts_on"]

    def __str__(self) -> str:
        return self.name


class StockMovement(models.Model):
    """Written by an event listener, never by hand.

    Nothing in the write path knows this model exists; a subscriber creates
    the row after the sale is saved.
    """

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="movements")
    change = models.IntegerField()
    reason = models.CharField(max_length=60)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at", "-pk"]

    def __str__(self) -> str:
        return f"{self.book}: {self.change:+d} ({self.reason})"


class CatalogNote(models.Model):
    """A note on any row, so a capability has something to probe for."""

    body = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    written_at = models.DateTimeField(auto_now_add=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ["-written_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self) -> str:
        return self.body[:40]

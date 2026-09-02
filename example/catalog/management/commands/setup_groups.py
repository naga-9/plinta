"""Create the demo's roles.

Plinta mints permissions and never grants them (§18.14a): which roles an
organisation has is a policy, so it belongs to the consumer. This is the
worked example of doing it.

Idempotent — run it after `migrate` **and after the screens are configured**.
Column permissions are minted when a `DataSourceField` is saved, so a role
built before that grants `view_sale` and none of its columns, and every table
renders empty. `seed_catalog` calls this command last for that reason.

**Two axes, deliberately.** A *domain* role is about the data (a manager sells
books); a *platform* role is about the screens (an author arranges dashboards).
They are orthogonal, and someone may hold both. Collapsing them is how a
dashboard editor ends up able to read every sale in the chain.
"""
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

#: What any signed-in person needs before a dashboard works at all. Two of
#: these fail silently when missed: without view_savedview personalisation
#: stops with no error, and without view_filterset the saved sets vanish.
PLINTA_READ = [
    "plinta_pages.view_page",
    "plinta_blocks.view_block",
    "plinta_blocks.view_savedview",
    "plinta_pages.view_filterset",
    "plinta_datasources.view_datasource",
]

#: The columns, named one at a time.
#:
#: They are not derived from the model permissions above, and the difference
#: matters: `view_book` says a person may see books, `view_book_price` says
#: they may see what one costs. Deriving the second from the first would mean
#: anybody who may open a screen may read every column on it, which is the
#: whole thing field permissions exist to prevent.
#:
#: A `change_` permission is minted only for a column its DataSourceField
#: marks `editable`, so the editable lists below are short on purpose.
CATALOG_COLUMNS = [
    "catalog.view_book_title",
    "catalog.view_book_author",
    "catalog.view_book_price",
    "catalog.view_book_published_on",
    "catalog.view_book_in_print",
    "catalog.view_promotion_name",
    "catalog.view_promotion_book__title",
    "catalog.view_promotion_starts_on",
    "catalog.view_promotion_ends_on",
    "catalog.view_promotion_discount_pct",
    "catalog.view_purchaseorder_ordered_on",
    "catalog.view_purchaseorder_supplier",
    "catalog.view_purchaseorder_store__name",
    "catalog.view_purchaseorder_status",
    "catalog.view_purchaseorder_expected_on",
    "catalog.view_purchaseorderline_order__supplier",
    "catalog.view_purchaseorderline_book__title",
    "catalog.view_purchaseorderline_quantity",
    "catalog.view_purchaseorderline_unit_cost",
    "catalog.view_purchaseorderline_line_total",
    "catalog.view_sale_sold_on",
    "catalog.view_sale_store__name",
    "catalog.view_sale_book__title",
    "catalog.view_sale_quantity",
    "catalog.view_sale_sale_total",
]

#: Reading plinta's own shareables. Seeing whose a view is, not changing it.
SHAREABLE_COLUMNS = [
    "plinta_blocks.view_savedview_name",
    "plinta_blocks.view_savedview_block",
    "plinta_blocks.view_savedview_owner",
    "plinta_blocks.view_savedview_is_default",
    "plinta_pages.view_filterset_name",
    "plinta_pages.view_filterset_page",
    "plinta_pages.view_filterset_owner",
    "plinta_pages.view_filterset_is_default",
]

CATALOG_READ = [
    "catalog.view_book",
    "catalog.view_store",
    "catalog.view_region",
    "catalog.view_sale",
    "catalog.view_purchaseorder",
    "catalog.view_purchaseorderline",
    "catalog.view_promotion",
]

#: Writing the data. `SalePolicy` narrows every one of these to the stores the
#: user manages — the model permission is the capability, the policy is the
#: scope (§5.6).
MANAGER = [
    "catalog.change_sale_quantity",
    # Their own views and filter sets. `change_savedview` edits one they own;
    # publishing it is `change_savedview_owner`, which they do not have.
    "plinta_blocks.add_savedview",
    "plinta_blocks.change_savedview",
    "plinta_blocks.delete_savedview",
    "plinta_blocks.change_savedview_name",
    "plinta_blocks.change_savedview_config",
    "plinta_blocks.change_savedview_is_default",
    "plinta_pages.add_filterset",
    "plinta_pages.change_filterset",
    "plinta_pages.change_filterset_name",
    "plinta_pages.change_filterset_values",
    "plinta_pages.change_filterset_is_default",
    "catalog.add_sale",
    "catalog.change_sale",
    "catalog.delete_sale",
    "catalog.add_purchaseorder",
    "catalog.change_purchaseorder",
    "catalog.add_purchaseorderline",
    "catalog.change_purchaseorderline",
]

#: Arranging the screens. Says nothing about the data.
AUTHOR = [
    "plinta_blocks.add_block",
    "plinta_blocks.change_block",
    "plinta_blocks.delete_block",
    "plinta_blocks.add_savedview",
    "plinta_blocks.change_savedview",
    "plinta_blocks.delete_savedview",
    # Publishing, which is a change to one field: `owner = None` is public.
    # An author may share a view and a filter set with everyone; a manager
    # below may save their own and not publish it. That distinction exists
    # only because the two models are registered as DataSources — a field
    # permission comes from a DataSourceField row and from nothing else
    # (§6.1b).
    "plinta_blocks.change_savedview_name",
    "plinta_blocks.change_savedview_config",
    "plinta_blocks.change_savedview_is_default",
    "plinta_pages.change_filterset_name",
    "plinta_pages.change_filterset_values",
    "plinta_pages.change_filterset_is_default",
    # And publishing: `owner = None` is public. A field permission, because
    # it is one field, and the act it names is not "edit a view" (§6.1b).
    "plinta_blocks.change_savedview_owner",
    "plinta_pages.change_filterset_owner",
    "catalog.change_book_title",
    "catalog.change_promotion_name",
    "plinta_pages.add_page",
    "plinta_pages.change_page",
    "plinta_pages.add_pageblock",
    "plinta_pages.change_pageblock",
    "plinta_pages.delete_pageblock",
    "plinta_pages.add_filterset",
    "plinta_pages.change_filterset",
]

#: Configuring the platform itself.
ADMINISTRATOR = [
    # Head office. Also what `StorePolicy` reads to decide who sees every
    # branch rather than only the ones they manage.
    "catalog.change_store",
    "plinta_datasources.add_datasource",
    "plinta_datasources.change_datasource",
    "plinta_datasources.add_datasourcefield",
    "plinta_datasources.change_datasourcefield",
    "plinta_datasources.delete_datasourcefield",
    "auth.view_permission",
    "auth.change_permission",
    "auth.view_group",
    "auth.change_group",
    "catalog.add_book",
    "catalog.change_book",
]

#: What every role starts from: the models, and the columns on them.
BASE = PLINTA_READ + CATALOG_READ + CATALOG_COLUMNS + SHAREABLE_COLUMNS

ROLES = {
    "Catalogue Viewer": BASE,
    "Store Manager": BASE + MANAGER,
    "Catalogue Author": BASE + AUTHOR,
    "Catalogue Administrator": BASE + MANAGER + AUTHOR + ADMINISTRATOR,
}


def permissions_for(names: list[str]) -> tuple[list[Permission], list[str]]:
    """Resolve `app_label.codename` strings, reporting any that do not exist.

    A codename nothing minted is held by nobody, so a role quietly missing one
    looks exactly like a bug in the feature it gates. Named rather than
    skipped.
    """
    found, missing = [], []
    for name in names:
        app_label, _, codename = name.partition(".")
        permission = Permission.objects.filter(
            content_type__app_label=app_label, codename=codename
        ).first()
        (found.append(permission) if permission else missing.append(name))
    return found, missing


class Command(BaseCommand):
    help = "Create the demo's four groups. Idempotent."

    def handle(self, *args, **options):
        for role, names in ROLES.items():
            group, created = Group.objects.get_or_create(name=role)
            permissions, missing = permissions_for(names)
            group.permissions.set(permissions)
            self.stdout.write(
                f"{'created' if created else 'updated'} {role}: "
                f"{len(permissions)} permissions"
            )
            for name in missing:
                self.stderr.write(f"  no such permission: {name}")

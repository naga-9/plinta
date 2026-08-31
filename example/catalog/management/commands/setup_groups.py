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

ROLES = {
    "Catalogue Viewer": PLINTA_READ + CATALOG_READ,
    "Store Manager": PLINTA_READ + CATALOG_READ + MANAGER,
    "Catalogue Author": PLINTA_READ + CATALOG_READ + AUTHOR,
    "Catalogue Administrator": (
        PLINTA_READ + CATALOG_READ + MANAGER + AUTHOR + ADMINISTRATOR
    ),
}


def column_permissions(names: list[str]) -> list[Permission]:
    """The column permissions implied by the model permissions in ``names``.

    `view_book` is the capability; `view_book_title` and its siblings are the
    columns, minted when somebody configures them (§6.9). Deriving them beats
    listing thirty codenames that change whenever a screen does — and it is
    why this command runs **after** `seed_catalog`: a permission that has not
    been minted cannot be granted.
    """
    wanted = []
    for name in names:
        app_label, _, codename = name.partition(".")
        action, _, model = codename.partition("_")
        if action not in {"view", "change"} or not model:
            continue
        wanted += list(
            Permission.objects.filter(
                content_type__app_label=app_label,
                codename__startswith=f"{action}_{model}_",
            ).exclude(codename__contains="_instance_")
        )
    return wanted


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
            permissions += column_permissions(names)
            group.permissions.set(permissions)
            self.stdout.write(
                f"{'created' if created else 'updated'} {role}: "
                f"{len(permissions)} permissions"
            )
            for name in missing:
                self.stderr.write(f"  no such permission: {name}")

"""Build the demo from nothing: data, DataSources, blocks, pages, a menu.

**This recreates the demo; it does not sync configuration.** A live install
keeps its screens in the database, where people arrange them in the browser,
and a seeder that ran against one would clobber their work. A demo is
disposable — the point is that `migrate && seed_catalog && runserver` produces
the same thing every time — so here the code is the source and is committed,
so a new reader can see how a screen is put together.

Idempotent, and safe to re-run: everything is matched on its natural key.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from plinta.blocks.models import Block
from plinta.datasources.models import DataSource, DataSourceField, Format
from plinta.pages.models import MenuGroup, MenuSection, Page, PageBlock, PageFilter

from catalog.models import (
    Book,
    OrderStatus,
    Promotion,
    PurchaseOrder,
    PurchaseOrderLine,
    Region,
    Sale,
    Store,
)

TODAY = datetime.date.today()


def only_filters(page, *field_names):
    """Remove any control on ``page`` this seeder no longer defines.

    A seeder that only ever adds leaves yesterday's configuration behind: the
    Store filter moved from `store__name` to `store` and both then drew, one
    of them dead. Safe here because a demo is recreated rather than synced —
    a live install keeps its screens in the database, where people arrange
    them.
    """
    page.filters.exclude(field_name__in=field_names).delete()


def column(source, name, label, order, **options):
    """One DataSourceField. Saving it mints the column's permissions (§6.9)."""
    field, _ = DataSourceField.objects.update_or_create(
        data_source=source, field_name=name, defaults={"label": label, "order": order,
                                                       **options}
    )
    return field


def datasource(model, name, label, columns):
    source, _ = DataSource.objects.update_or_create(
        name=name,
        defaults={"label": label, "content_type": ContentType.objects.get_for_model(model)},
    )
    for order, (field_name, field_label, options) in enumerate(columns):
        column(source, field_name, field_label, order, **options)
    return source


def block(name, component, source, owner=None, **fields):
    obj, _ = Block.objects.update_or_create(
        name=name,
        owner=owner,
        defaults={"component_type": component, "data_source": source, **fields},
    )
    return obj


def place(page, blk, *, col, row, w, h, order, **fields):
    PageBlock.objects.update_or_create(
        page=page, block=blk,
        defaults={"column": col, "row": row, "width": w, "height": h,
                  "order": order, **fields},
    )


class Command(BaseCommand):
    help = "Recreate the demo: sample data, DataSources, blocks, pages and menu."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-users", action="store_true", help="Skip creating the demo logins."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.sample_data()
        sources = self.sources()
        pages = self.screens(sources)
        # After the columns, because they are what mint the field permissions a
        # role grants: built before them, every table renders empty. And before
        # the people, because that is when a group exists to put them in.
        call_command("setup_groups", verbosity=0)
        if not options["no_users"]:
            self.users()
        self.stdout.write(
            f"seeded {Book.objects.count()} books, {Sale.objects.count()} sales, "
            f"{len(sources)} data sources, {len(pages)} pages"
        )

    # --- the domain --------------------------------------------------------

    def sample_data(self):
        north, _ = Region.objects.get_or_create(code="N", defaults={"name": "North"})
        south, _ = Region.objects.get_or_create(code="S", defaults={"name": "South"})

        stores = {}
        for name, region in (("Hale Street", north), ("Fen End", north),
                             ("Marsh Lane", south)):
            stores[name], _ = Store.objects.get_or_create(
                name=name, defaults={"region": region, "opened_on": TODAY.replace(year=TODAY.year - 3)}
            )

        titles = [
            ("Dune", "Frank Herbert", "9780441013593", "9.99", 1965, True),
            ("Emma", "Jane Austen", "9780141439587", "6.50", 1815, True),
            ("Beloved", "Toni Morrison", "9781400033416", "11.25", 1987, True),
            ("Ariel", "Sylvia Plath", "9780571086269", "8.75", 1965, False),
            ("Ulysses", "James Joyce", "9780199535675", "14.00", 1922, True),
            ("Wolf Hall", "Hilary Mantel", "9780007230181", "12.50", 2009, True),
        ]
        books = {}
        for title, author, isbn, price, year, in_print in titles:
            books[title], _ = Book.objects.get_or_create(
                isbn=isbn,
                defaults={
                    "title": title, "author": author, "price": Decimal(price),
                    "published_on": datetime.date(year, 1, 1), "in_print": in_print,
                },
            )

        if not Sale.objects.exists():
            for offset, (title, store_name, quantity) in enumerate([
                ("Dune", "Hale Street", 3), ("Emma", "Hale Street", 1),
                ("Beloved", "Fen End", 2), ("Dune", "Fen End", 5),
                ("Wolf Hall", "Marsh Lane", 4), ("Ulysses", "Marsh Lane", 1),
                ("Emma", "Marsh Lane", 2), ("Beloved", "Hale Street", 6),
            ]):
                Sale.objects.create(
                    book=books[title], store=stores[store_name],
                    sold_on=TODAY - datetime.timedelta(days=offset * 3),
                    quantity=quantity, unit_price=books[title].price,
                )

        if not PurchaseOrder.objects.exists():
            for supplier, store_name, status in (
                ("Gardners", "Hale Street", OrderStatus.PLACED),
                ("Bertrams", "Fen End", OrderStatus.DRAFT),
                ("Gardners", "Marsh Lane", OrderStatus.RECEIVED),
            ):
                order = PurchaseOrder.objects.create(
                    store=stores[store_name], supplier=supplier, ordered_on=TODAY,
                    expected_on=TODAY + datetime.timedelta(days=14), status=status,
                )
                for title in ("Dune", "Emma"):
                    PurchaseOrderLine.objects.create(
                        order=order, book=books[title], quantity=10,
                        unit_cost=books[title].price * Decimal("0.6"),
                    )

        if not Promotion.objects.exists():
            Promotion.objects.create(
                name="Summer classics", book=books["Emma"], starts_on=TODAY,
                ends_on=TODAY + datetime.timedelta(days=30),
                discount_pct=Decimal("15.00"),
            )

    # --- what plinta may show ----------------------------------------------

    def sources(self):
        return {
            "books": datasource(Book, "books", "Books", [
                ("title", "Title", {"filterable": True, "editable": True}),
                ("author", "Author", {"filterable": True}),
                ("price", "Price", {"format": Format.NONE, "decimals": 2,
                                    "prefix": "£", "sorter": "number"}),
                ("published_on", "Published", {"format": Format.DATE, "sorter": "date"}),
                ("in_print", "Status", {"renderer": "stock_badge"}),
            ]),
            "sales": datasource(Sale, "sales", "Sales", [
                ("sold_on", "Sold", {"format": Format.DATE, "sorter": "date",
                                     "renderer": "", "filterable": True}),
                ("store__name", "Store", {"renderer": "store_link", "filterable": True}),
                ("book__title", "Book", {"filterable": True}),
                ("quantity", "Qty", {"sorter": "number", "editable": True}),
                ("sale_total", "Total", {"decimals": 2, "prefix": "£",
                                         "sorter": "number",
                                         "thousands_separator": True}),
            ]),
            "orders": datasource(PurchaseOrder, "orders", "Purchase orders", [
                ("ordered_on", "Ordered", {"format": Format.DATE, "sorter": "date"}),
                ("supplier", "Supplier", {"filterable": True}),
                ("store__name", "Store", {"filterable": True}),
                ("status", "Status", {"filterable": True}),
                ("expected_on", "Expected", {"format": Format.DATE, "sorter": "date"}),
            ]),
            "order_lines": datasource(PurchaseOrderLine, "order_lines", "Order lines", [
                ("order__supplier", "Supplier", {}),
                ("book__title", "Book", {}),
                ("quantity", "Qty", {"sorter": "number"}),
                ("unit_cost", "Unit cost", {"decimals": 2, "prefix": "£",
                                            "sorter": "number"}),
                ("line_total", "Total", {"decimals": 2, "prefix": "£",
                                         "sorter": "number"}),
            ]),
            "promotions": datasource(Promotion, "promotions", "Promotions", [
                ("name", "Campaign", {"editable": True}),
                ("book__title", "Book", {}),
                ("starts_on", "From", {"format": Format.DATE, "sorter": "date"}),
                ("ends_on", "To", {"format": Format.DATE, "sorter": "date"}),
                ("discount_pct", "Discount", {"decimals": 1, "suffix": "%",
                                              "sorter": "number"}),
            ]),
        }

    # --- the screens -------------------------------------------------------

    def screens(self, sources):
        section, _ = MenuSection.objects.get_or_create(
            name="Bookshop", defaults={"order": 1}
        )
        trading, _ = MenuGroup.objects.get_or_create(
            section=section, name="Trading", defaults={"order": 1}
        )
        buying, _ = MenuGroup.objects.get_or_create(
            section=section, name="Buying", defaults={"order": 2}
        )

        pages = {}

        # Catalogue --------------------------------------------------------
        pages["catalogue"], _ = Page.objects.update_or_create(
            slug="catalogue", owner=None,
            defaults={"name": "Catalogue", "menu_icon": "plinta:book",
                      "menu_group": trading, "menu_order": 1,
                      "description": "Every title the chain carries."},
        )
        place(pages["catalogue"],
              block("titles-in-print", "stat_catalog", sources["books"],
                    config={"label": "Titles in print"},
                    queryset_modifier="in_print_only"),
              col=0, row=0, w=3, h=2, order=0, title="In print")
        place(pages["catalogue"],
              block("books-table", "table_plinta", sources["books"],
                    config={"page_size": 25, "sort": [{"field": "title"}],
                            "striped": True}),
              col=3, row=0, w=9, h=6, order=1, title="Every title")
        # An operator the viewer may change. The author picks which are on
        # offer; the query string can only choose from them, never write one.
        PageFilter.objects.update_or_create(
            page=pages["catalogue"], field_name="title",
            defaults={"label": "Title", "lookup": "icontains", "order": 0,
                      "allowed_lookups": ["icontains", "exact", "istartswith"]},
        )
        PageFilter.objects.update_or_create(
            page=pages["catalogue"], field_name="in_print",
            defaults={"label": "In print", "widget": "boolean_plinta", "order": 1},
        )
        # Two bounds, so the catalogue can be narrowed to a publication window.
        PageFilter.objects.update_or_create(
            page=pages["catalogue"], field_name="published_on",
            defaults={"label": "Published", "widget": "daterange_plinta", "order": 2},
        )
        only_filters(pages["catalogue"], "title", "in_print", "published_on")

        # Sales ------------------------------------------------------------
        pages["sales"], _ = Page.objects.update_or_create(
            slug="sales", owner=None,
            defaults={"name": "Sales", "menu_icon": "plinta:cart", "menu_group": trading, "menu_order": 2,
                      "description": "What sold, and where."},
        )
        place(pages["sales"],
              block("revenue", "stat_catalog", sources["sales"],
                    config={"label": "Revenue", "total_field": "sale_total",
                            "prefix": "£", "decimals": 2}),
              col=0, row=0, w=3, h=2, order=0, title="This month")
        place(pages["sales"],
              block("recent-sales", "table_plinta", sources["sales"],
                    config={"page_size": 20, "striped": True}),
              col=3, row=0, w=9, h=6, order=1, title="Recent sales")
        # Two multi-selects, to show both halves of the behaviour.
        #
        # The options are the values *present in the sales this viewer can
        # see*: mira is offered Hale Street and noor Marsh Lane, and somebody
        # with no sales is offered nothing rather than a list of branches
        # whose rows they cannot reach.
        #
        # And each narrows the other. Choose a store and the book filter
        # offers only what sold there; choose a book and the store filter
        # offers only where it sold. Neither narrows itself, or the first
        # choice could not be changed.
        PageFilter.objects.update_or_create(
            page=pages["sales"], field_name="store",
            defaults={"label": "Store", "widget": "multiselect_plinta", "lookup": "in",
                      "data_source": sources["sales"], "order": 0},
        )
        PageFilter.objects.update_or_create(
            page=pages["sales"], field_name="book",
            defaults={"label": "Title", "widget": "multiselect_plinta", "lookup": "in",
                      "data_source": sources["sales"], "order": 1},
        )
        # Named windows rather than dates: "current month" keeps meaning this
        # month, where a date typed in September freezes there. Several may be
        # chosen and they OR together.
        PageFilter.objects.update_or_create(
            page=pages["sales"], field_name="sold_on",
            defaults={"label": "When", "widget": "relative_date_plinta",
                      "data_source": sources["sales"], "order": 2},
        )
        only_filters(pages["sales"], "store", "book", "sold_on")

        # Purchasing --------------------------------------------------------
        pages["purchasing"], _ = Page.objects.update_or_create(
            slug="purchasing", owner=None,
            defaults={"name": "Purchasing", "menu_icon": "plinta:package", "menu_group": buying, "menu_order": 1,
                      "description": "Orders still outstanding."},
        )
        place(pages["purchasing"],
              block("open-orders", "table_plinta", sources["orders"],
                    config={"striped": True}, queryset_modifier="open_orders"),
              col=0, row=0, w=12, h=4, order=0, title="Open orders")
        place(pages["purchasing"],
              block("order-lines", "table_plinta", sources["order_lines"],
                    config={"page_size": 15, "compact": True}),
              col=0, row=4, w=12, h=4, order=1, title="Order lines")

        # Promotions --------------------------------------------------------
        pages["promotions"], _ = Page.objects.update_or_create(
            slug="promotions", owner=None,
            defaults={"name": "Promotions", "menu_icon": "plinta:tag", "menu_group": trading, "menu_order": 3,
                      "description": "Campaigns you own, and the public ones."},
        )
        place(pages["promotions"],
              block("my-promotions", "table_plinta", sources["promotions"],
                    config={"striped": True}),
              col=0, row=0, w=12, h=5, order=0, title="Campaigns")

        return pages

    # --- somebody to sign in as --------------------------------------------

    def users(self):
        User = get_user_model()
        groups = {g.name: g for g in Group.objects.all()}
        people = [
            ("ada", "Catalogue Administrator", None),
            ("mira", "Store Manager", "Hale Street"),
            ("noor", "Store Manager", "Marsh Lane"),
            ("sam", "Catalogue Viewer", None),
        ]
        for username, role, store_name in people:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password("demo")  # noqa: S106 - a demo login
                user.save()
            if role in groups:
                user.groups.set([groups[role]])
            else:
                self.stderr.write(f"{username}: no {role} group to join")
            if store_name:
                Store.objects.get(name=store_name).managers.add(user)

        self.superuser()
        self.stdout.write("logins: ada, mira, noor, sam — password 'demo'")

    def superuser(self):
        """One account for Django's admin, kept apart from the four roles.

        A superuser is the permission engine's single bypass: both tiers stop
        applying, so every store's rows are visible at once. That is the
        opposite of what `mira` and `noor` demonstrate, which is why this is a
        fifth login rather than a flag on `ada` — administering the catalogue
        is a role built from grants, and this is an escape hatch.
        """
        User = get_user_model()
        root, created = User.objects.get_or_create(
            username="root", defaults={"is_staff": True, "is_superuser": True}
        )
        if created:
            root.set_password("demo")  # noqa: S106 - a demo login
            root.save()
        elif not (root.is_staff and root.is_superuser):
            # Re-running must repair it: a demo is disposable and the account
            # is worth nothing if a stray edit left it unable to sign in.
            root.is_staff = root.is_superuser = True
            root.save(update_fields=["is_staff", "is_superuser"])
        self.stdout.write("admin: root — password 'demo' — /admin/")

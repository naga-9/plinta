"""One command, and a consumer has an application.

This is the orchestrator (§13.2). It creates the menu the shipped screens hang
from, then calls **whichever per-app seeders are installed** — so a minimal
install seeds core's screens and nothing else, and installing
`contrib.notifications` later adds its page by re-running this.

**It delegates and does not build.** v1's orchestrator constructed the audit
viewer inline — a seven-field DataSource and three page filters — which put
one app's screen in the one file whose job is to call other apps. A seeder
belongs to the app whose screens it creates, so that uninstalling a package
takes its page with it and leaves core nothing to clean up.

**Discovered, not listed.** The seeders are found through Django's own command
registry, so a contrib package that ships one is called without core naming
it — the same rule the shell follows for links and the page header follows for
actions. Order is fixed here because the sections a page hangs from must exist
before the page does.

Idempotent, like every seeder it calls.
"""
from django.core.management import call_command, get_commands
from django.core.management.base import BaseCommand
from django.db import transaction

from plinta.pages.models import MenuGroup, MenuSection

#: The navigation the shipped screens hang from. Created here rather than by
#: each seeder, so two packages cannot disagree about what "Administration"
#: is ordered at.
SECTIONS = [
    ("Records", 10),
    ("Administration", 90),
]

#: `(section or None, group, order)`. A group with no section sits at the top
#: of the menu, which is what a small install wants.
GROUPS = [
    ("Records", "Records", 10),
    ("Administration", "Authoring", 20),
    ("Administration", "People", 30),
    ("Administration", "System", 40),
]

#: Called in this order, and only when present. Every one is a management
#: command, so a package ships a seeder the same way it ships anything else.
#:
#: `seed_shareables` runs first and is not a screen: it registers plinta's own
#: shareable models so their `owner` field has a permission (§6.1b). A page
#: seeded before it would be shareable by anybody.
SEEDERS = [
    "seed_shareables",
    "seed_users_page",
    "seed_audit_page",
    "seed_reports_page",
    "seed_organizations_page",
    "seed_labels_page",
    "seed_notifications_page",
    "seed_workflows_page",
]


class Command(BaseCommand):
    help = "Create the menu and every installed app's screens. Idempotent."

    def add_arguments(self, parser):
        parser.add_argument(
            "--menu-only",
            action="store_true",
            help="Create the menu sections and groups, and call nothing.",
        )

    def handle(self, *args, **options):
        self.menu()
        if options["menu_only"]:
            return

        available = get_commands()
        for name in SEEDERS:
            if name not in available:
                # Not an error: the package that owns it is not installed,
                # which is the whole point of asking rather than importing.
                continue
            self.stdout.write(f"→ {name}")
            call_command(name, verbosity=options.get("verbosity", 1))

        self.stdout.write(self.style.SUCCESS("platform pages ready"))

    @transaction.atomic
    def menu(self):
        """The sections and groups, by name so a rename is the consumer's."""
        sections = {}
        for name, order in SECTIONS:
            sections[name], _ = MenuSection.objects.get_or_create(
                name=name, defaults={"order": order}
            )
        for section, name, order in GROUPS:
            MenuGroup.objects.get_or_create(
                section=sections[section], name=name, defaults={"order": order}
            )

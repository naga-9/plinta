"""The shell app."""
from django.apps import AppConfig


class ShellConfig(AppConfig):
    name = "plinta.shell"
    label = "plinta_shell"
    verbose_name = "plinta shell"

    def ready(self):
        # The declared-dependency checks, registered wherever plinta is.
        from plinta.utils import checks as _dependency_checks  # noqa: F401
        # Imported for its side effect: registering the boot checks.
        from plinta.shell import checks  # noqa: F401
        from plinta.utils import icons

        icons.register_defaults()

        # The authoring screens are ordinary pages behind ordinary model
        # permissions, so they reach the sidebar the way a contrib app's do.
        from plinta.shell.links import register_shell_link

        register_shell_link(
            "data_sources",
            "Data sources",
            url_name="plinta:data_sources",
            permission="plinta_datasources.view_datasource",
            icon="table",
            section="Administration",
            group="Authoring",
            order=900,
        )
        register_shell_link(
            "blocks",
            "Blocks",
            url_name="plinta:block_list",
            permission="plinta_blocks.change_block",
            icon="dashboard",
            section="Administration",
            group="Authoring",
            order=910,
        )
        register_shell_link(
            "pages",
            "Pages",
            url_name="plinta:page_list",
            permission="plinta_pages.change_page",
            icon="dashboard",
            section="Administration",
            group="Authoring",
            order=920,
        )

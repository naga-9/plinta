"""The blocks app."""
from django.apps import AppConfig


class BlocksConfig(AppConfig):
    name = "plinta.blocks"
    label = "plinta_blocks"
    verbose_name = "plinta blocks"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from plinta.blocks import actions

        # Core's own: which saved view a block is drawn with. Registered
        # rather than built into the card, through the same door a contrib
        # export button uses.
        actions.register_block_action(
            "saved_view",
            template="plinta/blocks/view_picker.html",
            # Nothing to choose between is nothing to offer. Read from the
            # views the page already fetched, never queried here: one query
            # per block per action is how eight blocks become forty round
            # trips.
            when=lambda views=(), **kw: bool(views),
            order=10,
        )
        # The declared-dependency checks, registered wherever plinta is.
        from plinta.utils import checks as _dependency_checks  # noqa: F401
        # Imported for their side effects: registering the policies that make
        # blocks and saved views shareable, and the boot check.
        from plinta.blocks import checks, policies  # noqa: F401

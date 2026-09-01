"""The blocks app."""
from django.apps import AppConfig


def _may_add(block=None, user=None, **kwargs) -> bool:
    """Whether this viewer may create a row of this block's model.

    The model permission alone: the row does not exist yet, so there is no
    policy to ask about it, and the write refuses again on arrival.
    """
    from plinta.permissions import can

    source = getattr(block, "data_source", None)
    model = getattr(source, "model", None)
    if model is None or user is None:
        return False
    return can(user, "add", model)


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
        # And core's other: a record this block's DataSource is about. The
        # same form a pencil opens, asked for with no record — which is all
        # that separates "add" from "edit".
        actions.register_block_action(
            "add_record",
            template="plinta/blocks/add_record.html",
            when=_may_add,
            order=20,
        )
        # Saving what you are looking at. Separate from the picker, which
        # has nothing to choose between until this has been used once.
        actions.register_block_action(
            "manage_views",
            template="plinta/blocks/manage_views.html",
            permission="plinta_blocks.add_savedview",
            order=15,
        )
        from plinta.utils.assets import register_script

        register_script("plinta/js/view-default.js", order=200)
        # The declared-dependency checks, registered wherever plinta is.
        from plinta.utils import checks as _dependency_checks  # noqa: F401
        # Imported for their side effects: registering the policies that make
        # blocks and saved views shareable, and the boot check.
        from plinta.blocks import checks, policies  # noqa: F401

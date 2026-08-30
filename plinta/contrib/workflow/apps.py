"""The workflow app."""
from django.apps import AppConfig


class WorkflowConfig(AppConfig):
    name = "plinta.contrib.workflow"
    label = "plinta_workflow"
    verbose_name = "plinta workflow"
    default_auto_field = "django.db.models.BigAutoField"

    #: The state machine needs these two. An admin screen would add more, and
    #: arrives as a seeder rather than as a dependency of the machine.
    requires = ["plinta.events", "plinta.permissions", "plinta.blocks", "plinta.renderers"]

    #: Reading where a row has been needs a recorded history. With audit
    #: absent, `history()` returns nothing and the panel says so — the state
    #: machine is unaffected.
    enhances = ["plinta.contrib.audit"]

    def ready(self):
        from plinta.contrib.workflow import (  # noqa: F401
            capabilities,
            policies,
            renderers,
            signals,
        )

        signals.connect()
        capabilities.register()
        renderers.register()

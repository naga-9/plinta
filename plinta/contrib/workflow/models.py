"""Workflows, states and transitions — all of it data.

A state machine that lives in code needs a deploy to change; one that lives in
rows needs somebody with the permission. Which of those is right depends on the
consumer, and this app takes the second because the first needs no app at all.
"""
from __future__ import annotations

from django.core.validators import RegexValidator
from django.db import models

#: A state or transition code. Lowercase and stable: it is half of a
#: permission codename, so it is an identifier rather than a label.
CODE = RegexValidator(
    regex=r"^[a-z][a-z0-9_]*$",
    message="Must start with a lowercase letter and contain only lowercase "
    "letters, numbers and underscores.",
)


class Workflow(models.Model):
    """One state machine, bound to one model.

    Bound by content type rather than by inheritance, so the consumer's model
    knows nothing about this one.
    """

    name = models.CharField(max_length=100)
    code = models.SlugField(max_length=60, unique=True, validators=[CODE])
    content_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.CASCADE,
        related_name="workflows",
        help_text="The model this workflow governs.",
    )
    state_field = models.CharField(
        max_length=60,
        default="state",
        help_text="The model's own field holding the state code. A plain "
        "column, so it sorts and filters like any other.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def model(self):
        """The Django model, or None if its app has gone."""
        return self.content_type.model_class()

    def initial(self):
        """Where a new row starts, or None if no state says it does."""
        return self.states.filter(is_initial=True).first()


class WorkflowState(models.Model):
    """One place a row can be."""

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="states")
    code = models.CharField(max_length=60, validators=[CODE])
    label = models.CharField(max_length=100)
    #: A CSS class or token name. Core draws it and names no palette.
    colour = models.CharField(max_length=40, blank=True, default="")
    order = models.PositiveIntegerField(default=0)
    is_initial = models.BooleanField(
        default=False, help_text="Where a row starts when it has no state."
    )
    is_final = models.BooleanField(
        default=False, help_text="Nothing leaves this state."
    )

    class Meta:
        ordering = ["order", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["workflow", "code"], name="unique_state_code_per_workflow"
            )
        ]

    def __str__(self) -> str:
        return self.label


class WorkflowTransition(models.Model):
    """One permitted move, and what it takes to make it.

    Its permission is minted when it is saved and renamed in place when its
    states are — the same treatment a column's permission gets, and for the
    same reason: a grant points at a permission's primary key, so recreating
    one drops every grant on it silently.
    """

    workflow = models.ForeignKey(
        Workflow, on_delete=models.CASCADE, related_name="transitions"
    )
    from_state = models.ForeignKey(
        WorkflowState, on_delete=models.CASCADE, related_name="transitions_out"
    )
    to_state = models.ForeignKey(
        WorkflowState, on_delete=models.CASCADE, related_name="transitions_in"
    )
    label = models.CharField(
        max_length=100, blank=True, default="", help_text="The button's words."
    )
    order = models.PositiveIntegerField(default=0)
    requires_confirmation = models.BooleanField(default=False)
    guard = models.CharField(
        max_length=60,
        blank=True,
        default="",
        help_text="A registered guard's name. Unset means the permission and "
        "the row policy decide alone.",
    )

    class Meta:
        ordering = ["order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["workflow", "from_state", "to_state"],
                name="unique_transition_per_pair",
            )
        ]

    def __str__(self) -> str:
        return self.label or f"{self.from_state.code} → {self.to_state.code}"

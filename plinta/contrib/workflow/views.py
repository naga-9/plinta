"""Making a move from a screen.

One view. It refuses the same three ways `execute` does and says which, so a
button that cannot be pressed explains itself rather than failing silently.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from plinta.contrib.workflow import services
from plinta.contrib.workflow.models import WorkflowTransition


@login_required
@require_POST
def transition(request, pk: int):
    """Execute one transition on one row.

    POST only: a move is a write, and a write behind a GET is a link a crawler
    can follow.

    The row is found through the workflow's own content type rather than
    trusted from the request, so a caller cannot name a transition on one
    model and a row on another.
    """
    move = get_object_or_404(
        WorkflowTransition.objects.select_related(
            "workflow", "from_state", "to_state"
        ),
        pk=pk,
    )
    model = move.workflow.model
    if model is None:
        messages.error(request, "That workflow's model is not installed.")
        return redirect(request.POST.get("next") or "/")

    obj = get_object_or_404(model, pk=request.POST.get("record"))
    try:
        services.execute(obj, move, request.user, source="ui")
    except services.TransitionDenied as denied:
        messages.error(request, str(denied))
    else:
        messages.success(request, f"Moved to {move.to_state.label}.")
    return redirect(request.POST.get("next") or "/")

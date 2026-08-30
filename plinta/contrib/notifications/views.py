"""The two screens this app ships: the list, and the preferences.

Both are ordinary Django views reached by registered links, because neither is
a composition of blocks — there is nothing for a `Page` to arrange (§10.2).
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from plinta.contrib.notifications import channels
from plinta.contrib.notifications.models import Notification, NotificationPreference
from plinta.contrib.notifications.registry import registered as subscriptions
from plinta.permissions import allowed


def mine(user):
    """This viewer's notifications, newest first.

    Through `allowed`, so both permission tiers apply — the model permission
    and `NotificationPolicy`, which admits only the recipient's own.
    """
    return allowed(user, "view", Notification.objects.all())


@login_required
def notification_list(request):
    """Everything this viewer has been told."""
    notifications = list(mine(request.user)[:200])
    return render(
        request,
        "plinta/notifications/list.html",
        {"notifications": notifications,
         "unread": sum(1 for n in notifications if not n.is_read)},
    )


@login_required
def mark_read(request, pk: int):
    """Mark one as read and go back to it, or to the list.

    `get_object_or_404` over the viewer's own queryset, so somebody else's
    notification is not found rather than refused — the id is guessable, and
    a refusal would confirm it exists.
    """
    notification = get_object_or_404(mine(request.user), pk=pk)
    notification.mark_read()
    return redirect(notification.url or "notifications:list")


@login_required
def mark_all_read(request):
    mine(request.user).filter(read_at__isnull=True).update(read_at=timezone.now())
    return redirect("notifications:list")


@login_required
def preferences(request):
    """A grid of kinds by channels, and one checkbox each.

    Both axes come from their registries, so a package adding a channel adds a
    column here and one adding a subscription adds a row — neither touching
    this view.
    """
    kinds = sorted(subscriptions().values(), key=lambda s: s.name)
    available = [c for c in channels.registered() if channels.reachable(request.user, c)]

    if request.method == "POST":
        for kind in kinds:
            for channel in available:
                NotificationPreference.objects.update_or_create(
                    user=request.user,
                    kind=kind.name,
                    channel=channel.name,
                    defaults={
                        "enabled": f"{kind.name}:{channel.name}" in request.POST
                    },
                )
        return redirect("notifications:preferences")

    from plinta.contrib.notifications.delivery import wants

    rows = [
        {
            "kind": kind,
            "cells": [
                {"channel": channel, "enabled": wants(request.user, kind, channel)}
                for channel in available
            ],
        }
        for kind in kinds
    ]
    return render(
        request,
        "plinta/notifications/preferences.html",
        {"channels": available, "rows": rows},
    )

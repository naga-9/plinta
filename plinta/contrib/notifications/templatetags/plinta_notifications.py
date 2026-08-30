"""What the bell needs to draw itself.

A tag rather than a context processor: a processor would run on every page
whether or not the bell is drawn, and this app does not get to add a query to
screens that never show it.
"""
from django import template

from plinta.contrib.notifications.models import Notification
from plinta.permissions import allowed

register = template.Library()


@register.simple_tag(takes_context=True)
def unread_count(context) -> int:
    """How many the viewer has not read. Zero when nobody is signed in."""
    user = getattr(context.get("request"), "user", None)
    if user is None or not user.is_authenticated:
        return 0
    return allowed(user, "view", Notification.objects.filter(read_at__isnull=True)).count()

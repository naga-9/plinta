"""The demo's own screens.

Two, and both are ordinary Django views. Everything else a consumer sees is a
`Page` composed in the browser.
"""
from django.contrib.auth.decorators import permission_required
from django.shortcuts import redirect, render

from plinta.pages.models import Page
from plinta.permissions import allowed


def home(request):
    """Send a viewer to the first page they may open."""
    if not request.user.is_authenticated:
        return redirect("plinta:login")
    first = allowed(request.user, "view", Page.objects.filter(is_active=True)).first()
    if first is None:
        return render(request, "catalog/nowhere.html")
    return redirect(first.get_absolute_url())


@permission_required("catalog.change_book")
def catalogue_admin(request):
    """A screen with no composition to record, so it is a view and a shell
    link rather than a Page (§10.2)."""
    from catalog.models import Book

    return render(request, "catalog/admin.html", {"books": Book.objects.all()[:50]})

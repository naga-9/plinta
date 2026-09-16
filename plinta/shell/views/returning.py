"""Where a dialog's form sends the viewer back to."""
from __future__ import annotations

from urllib.parse import urlencode

from django.http import HttpRequest
from django.utils.http import url_has_allowed_host_and_scheme


def back_to(request: HttpRequest, fallback: str, **params: object) -> str:
    """The URL a saved form redirects to: what the opener said, else ``fallback``.

    The opener carries ``next`` — the page the layer was opened over, which
    for a detail page is the record's URL and not the page's own, where a
    redirect would find no record and 404 — and the editor keeps it in a
    hidden field. Checked to be this host's, so a ``next`` somebody typed
    cannot send a viewer elsewhere. ``params`` are added to it: the view
    just saved, the set just saved.
    """
    wanted = request.POST.get("next") or request.GET.get("next") or ""
    if not wanted or not url_has_allowed_host_and_scheme(
        wanted, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        wanted = fallback
    if params:
        wanted += ("&" if "?" in wanted else "?") + urlencode(params)
    return wanted

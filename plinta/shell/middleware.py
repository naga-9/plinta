"""The outermost gate: every request carries a real user, or is redirected.

Required, not optional. Every layer below assumes a request reached it with an
authenticated user, and a permission decision made for `AnonymousUser` is a
decision about nobody. Install it **after** `AuthenticationMiddleware`, which
is what puts `request.user` there in the first place — a system check reports
both mistakes (§10.4).
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import resolve_url


class LoginRequiredMiddleware:
    """Redirect an anonymous request unless its path is exempt.

    Exempt by default: the login URL, static and media, the API mount, and
    anything in ``PLINTA_LOGIN_EXEMPT_PREFIXES``.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._exempt: tuple[str, ...] | None = None

    def exempt_prefixes(self) -> tuple[str, ...]:
        """The path prefixes that never redirect.

        The API mount is exempt so django-ninja answers an XHR caller with its
        own JSON 401 rather than an HTML redirect the caller cannot read. It is
        read from the same setting that mounts the API, so the two cannot
        drift (§19.3).
        """
        if self._exempt is None:
            prefixes = {
                resolve_url(settings.LOGIN_URL),
                settings.STATIC_URL,
                getattr(settings, "MEDIA_URL", "") or "",
                getattr(settings, "PLINTA_API_PREFIX", "/api/"),
                *getattr(settings, "PLINTA_LOGIN_EXEMPT_PREFIXES", ()),
            }
            # Drop "" and "/": Django's default MEDIA_URL is "/", and a prefix
            # that matches every path would exempt the whole site.
            self._exempt = tuple(sorted(p for p in prefixes if p and p != "/"))
        return self._exempt

    def is_exempt(self, path: str) -> bool:
        """Whether this path is reachable without logging in."""
        return path.startswith(self.exempt_prefixes())

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and not user.is_authenticated
            and not self.is_exempt(request.path)
        ):
            return redirect_to_login(request.get_full_path())
        return self.get_response(request)

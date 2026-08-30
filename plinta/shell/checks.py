"""What must be true at boot for a request to reach a page with a real user.

This is the shell's check rather than one of `permissions`' (§5.13), which are
all about policy and codename registration: that layer does not know a
middleware exists.
"""
from __future__ import annotations

from django.core.checks import Error, register

MIDDLEWARE = "plinta.shell.middleware.LoginRequiredMiddleware"
AUTHENTICATION = "django.contrib.auth.middleware.AuthenticationMiddleware"


@register()
def check_login_required_middleware(app_configs=None, **kwargs) -> list[Error]:
    """`LoginRequiredMiddleware` is installed, and after `AuthenticationMiddleware`.

    Absent, every page below decides permissions for an anonymous user, which
    is a decision about nobody. Installed too early, `request.user` does not
    exist yet and the gate silently lets every request through — the worse of
    the two, because it looks like it is working.
    """
    from django.conf import settings

    installed = list(settings.MIDDLEWARE)
    if MIDDLEWARE not in installed:
        return [
            Error(
                "LoginRequiredMiddleware is not installed, so an anonymous "
                "request reaches pages that assume a real user.",
                hint=f"Add {MIDDLEWARE!r} to MIDDLEWARE, after {AUTHENTICATION!r}.",
                id="plinta.shell.E001",
            )
        ]

    if AUTHENTICATION in installed and installed.index(MIDDLEWARE) < installed.index(
        AUTHENTICATION
    ):
        return [
            Error(
                "LoginRequiredMiddleware runs before AuthenticationMiddleware, "
                "so request.user does not exist yet and nothing is gated.",
                hint=f"Move {MIDDLEWARE!r} after {AUTHENTICATION!r}.",
                id="plinta.shell.E002",
            )
        ]
    return []

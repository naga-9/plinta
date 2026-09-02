"""Who is calling: an API key, or an ordinary session.

Two credentials, one identity. A key resolves to a user and a session already
is one, so everything downstream — row policies, field permissions, tenancy —
asks the same question either way (§15.1).

Session is accepted so that a browser exploring the docs is the person signed
into the application, rather than needing a key to read their own data.
"""
from __future__ import annotations

from django.utils import timezone
from ninja.security import APIKeyHeader, django_auth

#: Not `Authorization: Bearer`, deliberately. That header is where a JWT or an
#: OAuth token goes, and a proxy or a library that assumes so may rewrite it.
#: A dedicated header cannot be mistaken for something it is not.
HEADER = "X-API-Key"

#: How stale `last_used_at` may get. A write per request would cost a row
#: update on every read to record something nobody needs to the second.
STALENESS = 3600


class ApiKeyAuth(APIKeyHeader):
    """Authenticate by `X-API-Key`, as the key's user."""

    param_name = HEADER

    def authenticate(self, request, key):
        from plinta.contrib.api.models import ApiKey, digest

        if not key:
            return None
        # Looked up by hash, so the plaintext is never compared against
        # anything stored and a database read cannot leak a working key.
        record = (
            ApiKey.objects.select_related("user").filter(hashed=digest(key)).first()
        )
        if record is None or not record.is_usable:
            return None
        # An inactive account keeps its keys and they stop working, which is
        # what disabling somebody is supposed to mean.
        if not getattr(record.user, "is_active", False):
            return None

        self.touch(record)
        # The request carries the user like any other authenticated request,
        # so a view cannot tell — and must not have to — which credential
        # arrived.
        request.user = record.user
        request.api_key = record
        return record.user

    def touch(self, record) -> None:
        """Record that the key was used, at most once an hour."""
        now = timezone.now()
        if (
            record.last_used_at is None
            or (now - record.last_used_at).total_seconds() > STALENESS
        ):
            type(record).objects.filter(pk=record.pk).update(last_used_at=now)


#: What every endpoint accepts. Order matters only for which is tried first.
AUTH = [ApiKeyAuth(), django_auth]

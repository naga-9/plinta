"""API keys, which authenticate **as a user**.

A key is a credential, not a permission system (§15.1). It resolves to a user
and every row policy, field permission and tenancy rule then applies unchanged
— so there is no parallel authorisation model to keep in step, and no way for
a key to read something its user could not.

Per-key field visibility therefore needs no feature: mint the key against a
service user whose role lacks the field permission.

**The key itself is never stored.** Only a hash of it, so a stolen database
does not hand over working credentials. The plaintext is returned once, at
creation, and cannot be recovered — which is the same promise every other
system that issues keys makes, and the only one worth making.
"""
from __future__ import annotations

import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

#: Enough entropy that guessing is not a strategy, short enough to paste.
KEY_BYTES = 32

#: What a key looks like, so one found in a log is recognisable as ours and
#: can be revoked rather than puzzled over.
PREFIX = "plinta_"

#: How much of the key is stored in the clear. Enough to tell two keys apart
#: in a list, far too little to reconstruct one.
HINT = 8


def generate() -> str:
    """A new key, in the form a caller sends it."""
    return PREFIX + secrets.token_urlsafe(KEY_BYTES)


def digest(key: str) -> str:
    """The stored form of ``key``.

    A plain SHA-256, deliberately, where a password would want a slow KDF: a
    key is 256 bits of machine-generated randomness with no structure to
    guess, so the attack a slow hash defends against — enumerating likely
    inputs — has nothing to enumerate. A slow hash here would only make every
    request slow.
    """
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class ApiKey(models.Model):
    """One credential, belonging to one user."""

    name = models.CharField(
        max_length=100,
        help_text="What this key is for, so it can be revoked knowingly.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
        help_text="Everything this key may do, it does as this person.",
    )
    #: Indexed and unique: it is what every authenticated request looks up.
    hashed = models.CharField(max_length=64, unique=True, db_index=True)
    hint = models.CharField(
        max_length=HINT + len(PREFIX),
        help_text="The start of the key, to tell it from another in a list.",
    )

    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Past this, the key stops working. Blank never expires.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    #: Written on use, so an unused key can be found and removed. Not exact
    #: to the second: a write per request would cost more than it tells.
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "API key"

    def __str__(self) -> str:
        return f"{self.name} ({self.hint}…)"

    @property
    def is_usable(self) -> bool:
        """Active, and not past its expiry."""
        if not self.is_active:
            return False
        return self.expires_at is None or self.expires_at > timezone.now()

    @classmethod
    def issue(cls, *, name: str, user, expires_at=None) -> tuple["ApiKey", str]:
        """Create a key, returning the row and the plaintext **once**.

        The caller must show the second value to whoever asked for it and then
        forget it. Nothing can recover it afterwards.
        """
        key = generate()
        record = cls.objects.create(
            name=name,
            user=user,
            hashed=digest(key),
            hint=key[: len(PREFIX) + HINT],
            expires_at=expires_at,
        )
        return record, key

"""The rule vocabulary.

A rule declares one condition twice over — as a ``Q`` that filters a queryset,
and as a predicate that tests one instance. Both come from a single
declaration, so a row surviving the filter always passes the check.

Rules compose with ``|``, ``&`` and ``~``.
"""
from __future__ import annotations

from collections.abc import Callable as CallableT
from collections.abc import Iterable
from typing import Any

from django.db.models import Q

#: Matches nothing. The deny path is a constant rather than a rule, so a policy
#: cannot compose one in and make a decision order-dependent (§5.18).
#: Matches no row, and matches it *explicitly*. A rule never returns a bare
#: `Q()` for either answer: Django's `Q()` is falsy and its combination
#: short-circuits, so `Q() | Q(store__in=[3])` is `Q(store__in=[3])` — the
#: branch that admitted everything silently replaced by the one that narrows.
#: A policy written `HasPerm("x") | FieldInUserSet(...)` would then list fewer
#: rows than `can()` admits one at a time, and the two halves would disagree.
DENY = Q(pk__in=[])

#: Matches every row. Always true for a saved row, so it composes under `|`,
#: `&` and `~` the way DENY does.
ALLOW = Q(pk__isnull=False)


def _authenticated(user) -> bool:
    return bool(getattr(user, "is_authenticated", False))


def _pks(items: Iterable[Any]) -> set:
    """Primary keys from model instances or from raw ids, whichever was given."""
    return {getattr(item, "pk", item) for item in items}


class Rule:
    """One condition, expressible as a queryset filter and as a predicate."""

    def to_q(self, user) -> Q:
        """The filter selecting rows this rule admits for ``user``."""
        raise NotImplementedError

    def evaluate(self, user, instance) -> bool:
        """Whether this rule admits ``instance`` for ``user``."""
        raise NotImplementedError

    def __or__(self, other: "Rule") -> "Rule":
        return _Or(self, other)

    def __and__(self, other: "Rule") -> "Rule":
        return _And(self, other)

    def __invert__(self) -> "Rule":
        return _Not(self)

    def __repr__(self) -> str:
        args = ", ".join(f"{k}={v!r}" for k, v in vars(self).items())
        return f"{type(self).__name__}({args})"

    @property
    def label(self) -> str:
        """One line naming this rule, for a decision trace.

        A combinator says only what it is, since its children are printed
        beneath it — repeating the whole subtree at every level makes the trace
        unreadable, which defeats the point of having one.
        """
        return repr(self)


class _Or(Rule):
    label = "OR — either branch admits"

    def __init__(self, a: Rule, b: Rule):
        self.a, self.b = a, b

    def to_q(self, user) -> Q:
        return self.a.to_q(user) | self.b.to_q(user)

    def evaluate(self, user, instance) -> bool:
        return self.a.evaluate(user, instance) or self.b.evaluate(user, instance)


class _And(Rule):
    label = "AND — both branches must admit"

    def __init__(self, a: Rule, b: Rule):
        self.a, self.b = a, b

    def to_q(self, user) -> Q:
        return self.a.to_q(user) & self.b.to_q(user)

    def evaluate(self, user, instance) -> bool:
        return self.a.evaluate(user, instance) and self.b.evaluate(user, instance)


class _Not(Rule):
    label = "NOT — inverts the branch below"

    def __init__(self, a: Rule):
        self.a = a

    def to_q(self, user) -> Q:
        return ~self.a.to_q(user)

    def evaluate(self, user, instance) -> bool:
        return not self.a.evaluate(user, instance)


def walk(rule: Rule):
    """Yield every rule in a tree, parents before children.

    Lets a check inspect what a policy composed without evaluating it.
    """
    yield rule
    for attr in ("a", "b"):
        child = getattr(rule, attr, None)
        if isinstance(child, Rule):
            yield from walk(child)


class Owner(Rule):
    """The row belongs to this user."""

    def __init__(self, field: str = "owner"):
        self.field = field

    def to_q(self, user) -> Q:
        return Q(**{self.field: user}) if _authenticated(user) else DENY

    def evaluate(self, user, instance) -> bool:
        if not _authenticated(user):
            return False
        return getattr(instance, f"{self.field}_id", None) == user.pk


class Public(Rule):
    """The row has **no owner**.

    It says nothing about the user, which is why it never stands alone for
    editing and always appears paired.
    """

    def __init__(self, field: str = "owner"):
        self.field = field

    def to_q(self, user) -> Q:
        return Q(**{f"{self.field}__isnull": True})

    def evaluate(self, user, instance) -> bool:
        return getattr(instance, f"{self.field}_id", None) is None


class HasPerm(Rule):
    """The user holds a Django model permission.

    User-scoped, so the filter is all-or-nothing: it narrows nothing about
    which rows, only whether any.
    """

    def __init__(self, codename: str):
        self.codename = codename

    def to_q(self, user) -> Q:
        return ALLOW if user.has_perm(self.codename) else DENY

    def evaluate(self, user, instance) -> bool:
        return user.has_perm(self.codename)


class InstancePerm(Rule):
    """A per-row grant, keyed on the primary key.

    Codename: ``{app}.{action}_{model}_instance_{pk}``. Keyed on the pk and
    never a name, because names are unique only per owner and a rename would
    otherwise move a grant to whatever took the old name.
    """

    def __init__(self, app: str, model: str, action: str):
        self.app, self.model, self.action = app, model, action

    def codename(self, pk) -> str:
        return f"{self.app}.{self.action}_{self.model}_instance_{pk}"

    def to_q(self, user) -> Q:
        if not _authenticated(user):
            return DENY
        prefix = self.codename("")
        granted = [p[len(prefix):] for p in user.get_all_permissions() if p.startswith(prefix)]
        return Q(pk__in=granted) if granted else DENY

    def evaluate(self, user, instance) -> bool:
        if not _authenticated(user):
            return False
        return user.has_perm(self.codename(instance.pk))


class FieldEq(Rule):
    """A field on the row equals a literal."""

    def __init__(self, field: str, value):
        self.field, self.value = field, value

    def to_q(self, user) -> Q:
        return Q(**{self.field: self.value})

    def evaluate(self, user, instance) -> bool:
        return getattr(instance, self.field) == self.value


class FieldInUserSet(Rule):
    """The row's ``field`` is in a set derived from the user.

    The abstract shape of structural scoping. It knows a field name and how to
    get a permitted set from a user; it never learns what the field points at,
    so a tenancy of companies, desks or households all use it unchanged.
    """

    def __init__(self, field: str, user_set: CallableT[[Any], Iterable[Any]]):
        self.field, self.user_set = field, user_set

    def to_q(self, user) -> Q:
        if not _authenticated(user):
            return DENY
        return Q(**{f"{self.field}__in": self.user_set(user)})

    def evaluate(self, user, instance) -> bool:
        if not _authenticated(user):
            return False
        # ``field_id`` first, and never as a getattr default: a default argument
        # is evaluated eagerly, so writing it that way loads the related object
        # on every call — one query per row for an id already in memory.
        attname = f"{self.field}_id"
        value = getattr(instance, attname) if hasattr(instance, attname) else getattr(
            instance, self.field, None
        )
        return value is not None and value in _pks(self.user_set(user))


class UserInM2M(Rule):
    """The user is in a user-valued many-to-many on the row."""

    def __init__(self, field: str):
        self.field = field

    def to_q(self, user) -> Q:
        return Q(**{self.field: user}) if _authenticated(user) else DENY

    def evaluate(self, user, instance) -> bool:
        if not _authenticated(user):
            return False
        return getattr(instance, self.field).filter(pk=user.pk).exists()


class GroupOverlap(Rule):
    """One of the user's groups is in a group-valued many-to-many on the row."""

    def __init__(self, field: str):
        self.field = field

    def to_q(self, user) -> Q:
        return Q(**{f"{self.field}__user": user}) if _authenticated(user) else DENY

    def evaluate(self, user, instance) -> bool:
        if not _authenticated(user):
            return False
        return getattr(instance, self.field).filter(user=user).exists()


class ParentModelPerm(Rule):
    """The user holds a model permission on the row's generic parent.

    For rows attached by ``content_type`` + ``object_id`` — an attachment, a
    comment — where the question is whether the user may act on what it hangs
    off rather than on the row itself.
    """

    def __init__(self, action: str):
        self.action = action

    def to_q(self, user) -> Q:
        if not _authenticated(user):
            return DENY
        from django.contrib.contenttypes.models import ContentType

        held = user.get_all_permissions()
        allowed = [
            ct.pk
            for ct in ContentType.objects.all()
            if f"{ct.app_label}.{self.action}_{ct.model}" in held
        ]
        return Q(content_type__in=allowed) if allowed else DENY

    def evaluate(self, user, instance) -> bool:
        if not _authenticated(user):
            return False
        ct = instance.content_type
        return user.has_perm(f"{ct.app_label}.{self.action}_{ct.model}")


class AllowAll(Rule):
    """Admits everything. The only rule that narrows nothing."""

    def to_q(self, user) -> Q:
        return ALLOW

    def evaluate(self, user, instance) -> bool:
        return True


class Callable(Rule):
    """Escape hatch: supply the two halves as functions.

    ``q_fn(user) -> Q`` and, optionally, ``eval_fn(user, instance) -> bool``.
    Without ``eval_fn`` the instance check runs the ``Q`` as a query, which is
    correct but costs a round trip per check.
    """

    def __init__(self, q_fn, eval_fn=None):
        self.q_fn, self.eval_fn = q_fn, eval_fn

    def to_q(self, user) -> Q:
        return self.q_fn(user)

    def evaluate(self, user, instance) -> bool:
        if self.eval_fn is not None:
            return self.eval_fn(user, instance)
        return type(instance).objects.filter(self.q_fn(user), pk=instance.pk).exists()

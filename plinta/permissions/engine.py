"""The three functions everything in plinta calls, and one diagnostic.

    can(user, action, target)        model or instance -> bool
    allowed(user, action, queryset)  -> queryset
    fields(user, action, model)      -> set of field names
    explain(user, action, target)    -> a decision trace, diagnostic only

Two tiers decide every action: the Django model permission, **and** the
registered policy. Both must hold. Stating that here rather than at each call
site is what keeps the superuser bypass in one place instead of seventeen.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field

from django.db.models import Model, QuerySet

from plinta.permissions.policies import policy_for
from plinta.permissions.rules import Rule


def _authenticated(user) -> bool:
    return bool(getattr(user, "is_authenticated", False))


def _is_superuser(user) -> bool:
    return bool(getattr(user, "is_superuser", False))


def _model_of(target) -> type[Model]:
    return target if isinstance(target, type) else type(target)


def model_codename(action: str, model: type[Model]) -> str:
    """``view`` + ``Book`` -> ``testapp.view_book``."""
    meta = model._meta
    return f"{meta.app_label}.{action}_{meta.model_name}"


def field_codename(action: str, model: type[Model], field_name: str) -> str:
    """``view`` + ``Book`` + ``price`` -> ``testapp.view_book_price``."""
    meta = model._meta
    return f"{meta.app_label}.{action}_{meta.model_name}_{field_name}"


def can(user, action: str, target) -> bool:
    """Whether ``user`` may perform ``action`` on ``target``.

    ``target`` is a model class — "may they at all?" — or an instance — "may
    they, on this row?". A model check consults tier 1 only; there is no row to
    put to a policy.
    """
    if _is_superuser(user):
        return True
    if not _authenticated(user):
        return False

    model = _model_of(target)
    if not user.has_perm(model_codename(action, model)):
        return False
    if isinstance(target, type):
        return True

    policy = policy_for(model)
    rule = policy.rule_for(action) if policy else None
    return True if rule is None else rule.evaluate(user, target)


def allowed(user, action: str, queryset: QuerySet) -> QuerySet:
    """The rows of ``queryset`` on which ``user`` may perform ``action``."""
    if _is_superuser(user):
        return queryset
    if not _authenticated(user):
        return queryset.none()

    model = queryset.model
    if not user.has_perm(model_codename(action, model)):
        return queryset.none()

    policy = policy_for(model)
    rule = policy.rule_for(action) if policy else None
    return queryset if rule is None else queryset.filter(rule.to_q(user))


def fields(user, action: str, model: type[Model]) -> set[str]:
    """Field names of ``model`` on which ``user`` may perform ``action``.

    Read from the granted permissions, so a field with no minted permission is
    absent — a column nobody declared is denied rather than allowed.
    """
    if _is_superuser(user):
        return minted_fields(action, model)
    if not _authenticated(user):
        return set()

    prefix = field_codename(action, model, "")
    return {p[len(prefix):] for p in user.get_all_permissions() if p.startswith(prefix)}


def minted_fields(action: str, model: type[Model]) -> set[str]:
    """Every field of ``model`` that has a permission for ``action``.

    Read from Django's own permission table, so this layer learns which columns
    are declared without importing the layer that declares them.
    """
    from django.contrib.auth.models import Permission

    prefix = f"{action}_{model._meta.model_name}_"
    return {
        perm.codename[len(prefix):]
        for perm in Permission.objects.filter(
            content_type__app_label=model._meta.app_label,
            codename__startswith=prefix,
        )
    }


# --------------------------------------------------------------------------
# Diagnostic


@dataclass
class Step:
    """One rule in the tree, and what it decided."""

    rule: str
    allowed: bool
    children: list["Step"] = dc_field(default_factory=list)

    def lines(self, depth: int = 0) -> list[str]:
        mark = "allow" if self.allowed else "deny "
        out = [f"{'  ' * depth}{mark}  {self.rule}"]
        for child in self.children:
            out.extend(child.lines(depth + 1))
        return out


@dataclass
class Decision:
    """Why an action was permitted or refused."""

    allowed: bool
    reason: str
    model_permission: bool | None = None
    policy: str | None = None
    trace: Step | None = None

    def __str__(self) -> str:
        head = f"{'ALLOWED' if self.allowed else 'DENIED'}: {self.reason}"
        return "\n".join([head, *(self.trace.lines(1) if self.trace else [])])


def _walk(rule: Rule, user, instance) -> Step:
    children = [
        _walk(child, user, instance)
        for attr in ("a", "b")
        if isinstance(child := getattr(rule, attr, None), Rule)
    ]
    return Step(rule=rule.label, allowed=rule.evaluate(user, instance), children=children)


def explain(user, action: str, target) -> Decision:
    """Trace the decision `can` would reach.

    Diagnostic only. `can` must never call this, so a trace that is expensive
    or incomplete can never change an answer.
    """
    if _is_superuser(user):
        return Decision(True, "superuser")
    if not _authenticated(user):
        return Decision(False, "not authenticated")

    model = _model_of(target)
    codename = model_codename(action, model)
    has_model_perm = user.has_perm(codename)
    if not has_model_perm:
        return Decision(False, f"lacks the model permission {codename}", model_permission=False)

    if isinstance(target, type):
        return Decision(True, f"holds {codename}; no row to check", model_permission=True)

    policy = policy_for(model)
    if policy is None:
        return Decision(
            True, f"holds {codename}; no policy registered for {model.__name__}",
            model_permission=True,
        )

    rule = policy.rule_for(action)
    name = type(policy).__name__
    if rule is None:
        return Decision(
            True, f"holds {codename}; {name} declares no rule for {action!r}",
            model_permission=True, policy=name,
        )

    trace = _walk(rule, user, target)
    return Decision(
        trace.allowed,
        f"{name}.{action} {'admits' if trace.allowed else 'refuses'} this row",
        model_permission=True,
        policy=name,
        trace=trace,
    )

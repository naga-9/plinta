"""The comments section, offered on every model that opts in.

A model opts in by declaring a `GenericRelation` to `Comment`. Nothing else:
no registry of commentable models to keep in step, and nothing to forget.
"""
from __future__ import annotations

from django.apps import apps
from django.contrib.contenttypes.fields import GenericRelation

from plinta.blocks.capabilities import register_capability


def commented_models() -> set[type]:
    """Every model declaring a GenericRelation to our Comment.

    Computed once per capability rather than once per model, which is what
    `prepare` exists for: this walks every installed model's fields.
    """
    from plinta.contrib.comments.models import Comment

    return {
        model
        for model in apps.get_models()
        for field in model._meta.get_fields()
        if isinstance(field, GenericRelation) and field.related_model is Comment
    }


def register() -> None:
    """Register the capability. Called from `AppConfig.ready()`."""
    register_capability(
        "comments",
        "Comments",
        # An unsaved row has nothing to hang a comment on.
        applies_to=lambda obj, user=None, **kw: getattr(obj, "pk", None) is not None,
        supports=lambda model, state=None, **kw: model in (state or set()),
        prepare=commented_models,
        template="plinta/comments/section.html",
        order=100,
    )

"""A consumer's models, for the contrib suite.

Separate from `testapp` because opting into a contrib capability is a
`GenericRelation` to that app's model — which makes the app **required** for
whoever opts in. A core suite that does not install contrib cannot hold a
model declaring one, and that constraint is the point rather than an
inconvenience.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models


class Article(models.Model):
    """Opted into comments, in one line, in the consumer's own model."""

    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    comments = GenericRelation("plinta_comments.Comment")
    #: Opting into a workflow is a column the consumer declares and a
    #: registration. No base class, and the state sorts like any other column.
    state = models.CharField(max_length=40, blank=True, default="")

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class Memo(models.Model):
    """Opted into nothing, so a probe has something to say no about."""

    title = models.CharField(max_length=200)

    def __str__(self) -> str:
        return self.title

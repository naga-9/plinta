"""Models the permission rules are exercised against.

The demo domain (SPEC §25.2), reduced to what the eleven rules need: an owner,
a nullable owner for the public case, a scoping FK, two M2Ms and a generic
parent.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Region(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self) -> str:
        # A filter option's label is `str(row)`, the same as Django's own
        # ModelChoiceField. Without this the list reads "Region object (1)".
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=200)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    region = models.ForeignKey(Region, null=True, blank=True, on_delete=models.SET_NULL)
    in_print = models.BooleanField(default=True)
    watchers = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="watched_books")
    #: How a model opts into a capability: the relation is declared here, and
    #: the capability's probe reads what points at it.
    notes = GenericRelation("testapp.Note")
    reader_groups = models.ManyToManyField("auth.Group", related_name="readable_books")


class Note(models.Model):
    """Attached to any row by content type — for ParentModelPerm."""

    body = models.TextField(blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")

"""Models the permission rules are exercised against.

The demo domain (SPEC §25.2), reduced to what the eleven rules need: an owner,
a nullable owner for the public case, a scoping FK, two M2Ms and a generic
parent.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Region(models.Model):
    name = models.CharField(max_length=50)


class Book(models.Model):
    title = models.CharField(max_length=200)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    region = models.ForeignKey(Region, null=True, blank=True, on_delete=models.SET_NULL)
    in_print = models.BooleanField(default=True)
    watchers = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="watched_books")
    reader_groups = models.ManyToManyField("auth.Group", related_name="readable_books")


class Note(models.Model):
    """Attached to any row by content type — for ParentModelPerm."""

    body = models.TextField(blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")

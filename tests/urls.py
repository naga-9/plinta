"""URLs for plinta's own suite. A consuming project supplies its own."""
from django.urls import include, path

urlpatterns = [path("", include("plinta.shell.urls"))]

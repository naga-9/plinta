"""The demo's URLs. plinta is mounted whole; catalog adds its own screen."""
from django.urls import include, path

from catalog import views

urlpatterns = [
    path("", views.home, name="home"),
    path("catalogue-admin/", views.catalogue_admin, name="catalogue_admin"),
    path("", include("plinta.shell.urls")),
]

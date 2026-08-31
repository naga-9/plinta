"""The demo's URLs. plinta is mounted whole; catalog adds its own screen."""
from django.contrib import admin
from django.urls import include, path

from catalog import views

urlpatterns = [
    path("", views.home, name="home"),
    path("catalogue-admin/", views.catalogue_admin, name="catalogue_admin"),
    # Django's admin, for editing users and groups. LoginRequiredMiddleware
    # sends an anonymous visitor to plinta's login rather than the admin's, so
    # there is one sign-in for the site; the admin still requires is_staff.
    path("admin/", admin.site.urls),
    path("", include("plinta.shell.urls")),
]

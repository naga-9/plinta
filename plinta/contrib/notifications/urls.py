"""Mounted by the consuming project:

    path("notifications/", include("plinta.contrib.notifications.urls")),
"""
from django.urls import path

from plinta.contrib.notifications import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("preferences/", views.preferences, name="preferences"),
    path("<int:pk>/read/", views.mark_read, name="mark_read"),
    path("read-all/", views.mark_all_read, name="mark_all_read"),
]

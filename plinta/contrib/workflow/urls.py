"""Mounted by the consuming project:

    path("workflow/", include("plinta.contrib.workflow.urls")),
"""
from django.urls import path

from plinta.contrib.workflow import views

app_name = "workflow"

urlpatterns = [
    path("transition/<int:pk>/", views.transition, name="transition"),
]

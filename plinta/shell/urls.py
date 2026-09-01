"""The shell's URLs: authentication, and the pages a viewer opens.

Mounted by the consuming project with ``path("", include("plinta.shell.urls"))``.
"""
from django.contrib.auth import views as auth_views
from django.urls import path

from plinta.shell import views

app_name = "plinta"

urlpatterns = [
    # The id resolves the page; the slug is decorative and is not checked, so
    # a rename does not break a link someone shared (§9.0).
    path("pages/<int:pk>-<slug:slug>/", views.page_view, name="page"),
    path("pages/<int:pk>/", views.page_view, name="page_by_id"),
    # Private UI transport (§15.4): what each control should offer given the
    # others' current selections, so the cascade happens while choosing.
    path("pages/<int:pk>/filter-options/", views.filter_options,
         name="filter_options"),
    # The rows one card fetches. Placement-scoped, so the view and the context
    # filter are read from the row rather than trusted from the query string.
    path("pages/<int:pk>/blocks/<int:placement>/data/", views.block_data,
         name="block_data"),
    # A detail page: the record in the path, so the URL is shareable and the
    # page is what somebody sends a colleague.
    path("pages/<int:pk>-<slug:slug>/<str:record>/", views.page_view, name="record"),
    path("pages/<int:pk>/<str:record>/", views.page_view, name="record_by_id"),
    path("accounts/login/", auth_views.LoginView.as_view(
        template_name="plinta/auth/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/password_reset/", auth_views.PasswordResetView.as_view(
        template_name="plinta/auth/password_reset.html"), name="password_reset"),
    path("accounts/password_reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="plinta/auth/password_reset_done.html"),
        name="password_reset_done"),
    path("accounts/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="plinta/auth/password_reset_confirm.html"),
        name="password_reset_confirm"),
    path("accounts/reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="plinta/auth/password_reset_complete.html"),
        name="password_reset_complete"),
]

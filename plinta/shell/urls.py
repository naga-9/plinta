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
    # The saved filter sets on a page. Page-scoped, because a filter set
    # belongs to the bar and the bar belongs to the page.
    path("pages/<int:pk>/filters/", views.page_filters, name="page_filters"),
    # The rows one card fetches. Placement-scoped, so the view and the context
    # filter are read from the row rather than trusted from the query string.
    path("pages/<int:pk>/blocks/<int:placement>/data/", views.block_data,
         name="block_data"),
    # And the write half. The same placement, so a write cannot reach a card
    # a read could not.
    path("pages/<int:pk>/blocks/<int:placement>/write/", views.block_write,
         name="block_write"),
    # What a relation column may be set to, when there are too many to send
    # with the columns.
    path("pages/<int:pk>/blocks/<int:placement>/options/<str:field>/",
         views.block_options, name="block_options"),
    # The form a card opens, for one record or for none. The same form a
    # detail page draws, asked for after the page has loaded.
    path("pages/<int:pk>/blocks/<int:placement>/form/", views.block_form,
         name="block_form"),
    # Managing the saved views on a card's block.
    path("pages/<int:pk>/blocks/<int:placement>/views/", views.block_views,
         name="block_views"),
    # Above the record routes: `pages/<pk>/<record>/` would otherwise match
    # "compose" and "positions" as record ids.
    path("pages/", views.pages, name="page_list"),
    path("pages/<int:pk>/compose/", views.page_composer, name="page_composer"),
    # What a drag posts to. Core owns the rule; contrib.composer owns the drag.
    path("pages/<int:pk>/positions/", views.page_positions, name="page_positions"),
    # A detail page: the record in the path, so the URL is shareable and the
    # page is what somebody sends a colleague.
    path("pages/<int:pk>-<slug:slug>/<str:record>/", views.page_view, name="record"),
    path("pages/<int:pk>/<str:record>/", views.page_view, name="record_by_id"),
    # The authoring screens (§12). Ordinary permission-gated pages, not an
    # admin: `view_datasource` is what makes this one visible.
    path("data-sources/", views.data_sources, name="data_sources"),
    path("data-sources/<int:pk>/", views.data_source, name="data_source"),
    path("blocks/", views.blocks, name="block_list"),
    path("blocks/<int:pk>/", views.block_inspector, name="block_inspector"),
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

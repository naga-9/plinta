"""Where the API is mounted.

The consumer chooses the path — a library must not declare a version whose
path somebody else owns (§15.5) — so this ships the `NinjaAPI` and the project
includes it wherever it likes:

    path("api/v1/", include("plinta.contrib.api.urls")),
"""
from django.urls import path
from ninja import NinjaAPI

from plinta.contrib.api.auth import AUTH
from plinta.contrib.api.router import register_errors, router

#: Namespaced so two plinta APIs, or a consumer's own, can coexist.
api = NinjaAPI(
    title="plinta data API",
    version="1.0.0",
    urls_namespace="plinta_api",
    auth=AUTH,
    description=(
        "Generated from the DataSource registry. Every response is narrowed "
        "by the caller's permissions; there is no second gate."
    ),
)
api.add_router("/", router)
register_errors(api)

urlpatterns = [path("", api.urls)]

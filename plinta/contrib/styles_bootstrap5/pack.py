"""The Bootstrap 5 mapping, and what it cannot reach.

Installed by listing this app and setting::

    PLINTA_STYLE_PACK = "bootstrap5"

Bootstrap's own CSS is the consumer's to load: this package ships a mapping,
not a vendored stylesheet. Where they load it from — a CDN, npm, their own
build — is theirs to decide, and vendoring it would make that decision for
them.

**What a mapping cannot do.** Three of plinta's structures already match
Bootstrap's, which is why they need only a rename:

    ours                        Bootstrap
    .pl-card > .pl-card__body   .card > .card-body
    .pl-pager ul > li > a       .pagination > .page-item > .page-link
    .pl-field > label + input   .mb-3 > .form-label + .form-control

That is not luck — a card with a padded body and a pager that is a list of
links are the shapes those things should have had anyway.

What is left over is listed in `RESIDUE` below, and needs a template
override rather than a class name. A pack is honest about that: silently
mapping something a class cannot fix produces a screen that looks broken
with no error to explain it.
"""
from __future__ import annotations

#: What this pack cannot express as a class name, and what a project wanting
#: it must override. Read by the system check so the gap is stated at boot
#: rather than discovered on a screen.
RESIDUE = {
    "plinta/shell/topbar.html": "Bootstrap's navbar wants .navbar > .container-fluid",
    "plinta/pages/filter_bar.html": "an inline form wants .row > .col-auto per control",
}

CLASSES = {
    # shell — Bootstrap has no opinion about a sidebar grid, so these keep
    # plinta's own layout classes and only the contents are restyled.
    "menu": "nav nav-pills flex-column",
    "menu_item": "nav-item",
    "menu_link": "nav-link",
    "menu_link_active": "active",
    "menu_heading": "text-uppercase text-secondary small fw-semibold px-3 mt-3 mb-1",
    "menu_group_name": "text-secondary small px-3",
    "topbar_actions": "d-flex align-items-center gap-2 ms-auto",
    # card
    # Bootstrap's own nav-tabs are markup-compatible: nav > nav-item > nav-link.
    "tabs_list": "nav nav-tabs",
    "tabs_item": "nav-item",
    "tabs_link": "nav-link",
    "tabs_link_active": "active",
    "card": "card",
    "card_header": "card-header d-flex align-items-center",
    "card_title": "h6 mb-0",
    "card_actions": "ms-auto d-flex gap-1",
    "card_body": "card-body",
    # table
    "table_wrap": "table-responsive",
    "table": "table table-hover align-middle mb-0",
    "table_striped": "table-striped",
    "table_compact": "table-sm",
    "table_bordered": "table-bordered",
    "table_sort": "link-body-emphasis text-decoration-none",
    "table_sort_active": "fw-bold",
    "table_empty": "text-center text-secondary",
    # pager
    "pager": "d-flex align-items-center gap-2 px-3 py-2 border-top",
    "pager_status": "text-secondary small",
    "pager_list": "pagination pagination-sm mb-0 ms-auto",
    "pager_item": "page-item",
    "pager_link": "page-link",
    # forms
    "field": "mb-3",
    "label": "form-label",
    "input": "form-control",
    "select": "form-select",
    "textarea": "form-control",
    "checkbox": "form-check-input",
    "help": "form-text",
    "error": "invalid-feedback d-block",
    "filters_actions": "d-flex align-items-end gap-2",
    # buttons
    "btn": "btn btn-outline-secondary",
    "btn_primary": "btn-primary",
    "btn_danger": "btn-danger",
    "btn_ghost": "btn-link",
    "btn_sm": "btn-sm",
    # feedback
    "alert": "alert",
    "alert_info": "alert-info",
    "alert_success": "alert-success",
    "alert_warning": "alert-warning",
    "alert_danger": "alert-danger",
    "chip": "badge text-bg-secondary",
    "chip_success": "text-bg-success",
    "chip_warning": "text-bg-warning",
    "chip_danger": "text-bg-danger",
    "chip_info": "text-bg-info",
    "chip_neutral": "text-bg-secondary",
    "muted": "text-secondary",
    "spinner": "spinner-border spinner-border-sm",
    # layout
    "stack": "vstack gap-3",
    "row": "d-flex align-items-center gap-2",
    "spacer": "ms-auto",
    "visually_hidden": "visually-hidden",
}


def register() -> None:
    """Put the mapping in the registry. Called from `AppConfig.ready()`."""
    from plinta.utils.styles import register_style_pack

    register_style_pack("bootstrap5", CLASSES)

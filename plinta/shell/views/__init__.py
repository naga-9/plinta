"""The views the shell serves.

Three files, one per kind of screen: `page` — a page and what surrounds it;
`card` — the conversation one card has with the server; `authoring` — the
screens that make pages. Every view is re-exported here, so `urls.py` names
`views.page_view` whichever file it lives in. (Singular file names, because
`pages` and `blocks` are views.)

A page is resolved by **id**; the slug in the URL is decorative and is not
checked, so renaming a page does not break a link someone shared (§9.0).
"""
from plinta.shell.views.authoring import (
    block_inspector,
    blocks,
    data_source,
    data_sources,
    page_composer,
    page_positions,
    pages,
)
from plinta.shell.views.card import (
    block_data,
    block_form,
    block_options,
    block_views,
    block_write,
    placement_of,
)
from plinta.shell.views.page import (
    FILTER_TARGETS,
    RESERVED,
    bound_record,
    cards_asked_for,
    chosen_set,
    closes_a_layer,
    home,
    page_filters,
    page_view,
    submitted_filters,
    visible_page,
)

__all__ = [
    "FILTER_TARGETS",
    "RESERVED",
    "block_data",
    "block_form",
    "block_inspector",
    "block_options",
    "block_views",
    "block_write",
    "blocks",
    "bound_record",
    "cards_asked_for",
    "chosen_set",
    "closes_a_layer",
    "data_source",
    "data_sources",
    "home",
    "page_composer",
    "page_filters",
    "page_positions",
    "page_view",
    "pages",
    "placement_of",
    "submitted_filters",
    "visible_page",
]

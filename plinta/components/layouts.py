"""Where a consumer says how a form is arranged.

Forms get complicated in ways a config field cannot express — three across
here, a full-width note there, a fieldset around two of them — so past a point
the honest answer is a template. This is the door for one.

    register_form_layout("book", "catalog/book_form.html")

A **registered key**, not a path typed into the block's config. A template name
stored in a row is a string in the database that decides what code runs, and
the same species has been refused twice already: `queryset_modifier` must be a
registered name rather than a dotted path, and `editor_queryset_filter` was
dropped partly for being an arbitrary filter living in configuration.

A layout owns the **body** and nothing else. The mount, the payload, the field
names, the submit and the error plumbing stay with the component, because a
layout that owned them could get one subtly wrong and the form would render
perfectly and silently never save. The worst a layout can do is leave a field
out, which is visible.
"""
from __future__ import annotations

import re

NAME = re.compile(r"[a-z][a-z0-9_]*")

#: The stacked one, used when a block names no layout.
DEFAULT = "plinta/components/form_body.html"

_registry: dict[str, str] = {}


class FormLayoutError(Exception):
    """A layout could not be registered."""


def register_form_layout(name: str, template: str) -> str:
    """Offer ``template`` as the body of a form, under ``name``.

    Raises:
        FormLayoutError: the name is taken or is not a lowercase key.
    """
    if not NAME.fullmatch(name or ""):
        raise FormLayoutError(
            f"{name!r} is not a layout name: lowercase, digits and underscores."
        )
    if name in _registry:
        raise FormLayoutError(
            f"{name!r} is already registered as {_registry[name]!r}. "
            f"registered: {', '.join(sorted(_registry)) or 'none'}"
        )
    if not template:
        raise FormLayoutError(f"{name!r} names no template.")
    _registry[name] = template
    return template


def get(name: str) -> str:
    """The template for ``name``, or the default where there is none.

    Never raises. A layout arrives from a saved block, and the app that
    registered it may since have been uninstalled — the same event that turns
    a component into an empty slot rather than an exception. The form still
    draws, stacked, and `check_form_layouts` is what says so out loud.
    """
    return _registry.get(name or "", DEFAULT)


def registered() -> list[str]:
    return sorted(_registry)

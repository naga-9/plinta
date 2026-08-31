"""Which class names the markup carries.

Plinta draws its own markup and names it `pl-*`. A **style pack** swaps those
names for somebody else's, so a project already using Bootstrap or Tailwind
gets screens that look like the rest of their application without forking a
template.

Called a style pack rather than a theme because `data-theme` already means
light or dark, and the two are unrelated: a Bootstrap pack still has both.

**A pack is class names only.** Where a framework needs a different *shape* —
Fomantic's pagination is `div`/`a` where ours is `ul`/`li`, and Bulma puts
prev and next outside the list — a class map cannot help and the pack
overrides the template instead. That residue is the reason packs are not the
whole answer, and the reason our own markup is chosen for its semantics rather
than to match anybody.

Lives at layer 1 because everything that emits markup needs it: the HTML
renderer, components, and the shell's templates.
"""
from __future__ import annotations

import re

NAME = re.compile(r"[a-z][a-z0-9_]*")

#: Every class name the markup emits, and what plinta's own stylesheet calls
#: it. A pack overrides the keys it cares about; the rest stay ours, so a pack
#: that only restyles buttons is four lines rather than a hundred.
DEFAULT: dict[str, str] = {
    # shell
    "shell": "pl-shell",
    "shell_collapsed": "pl-shell--collapsed",
    "main": "pl-main",
    "main_inner": "pl-main__inner",
    "sidebar": "pl-sidebar",
    "menu": "pl-menu",
    "menu_item": "pl-menu__item",
    "menu_link": "pl-menu__link",
    "menu_link_active": "is-active",
    "menu_section": "pl-sidebar__section",
    "menu_heading": "pl-sidebar__heading",
    "menu_group": "pl-sidebar__group",
    "menu_group_name": "pl-sidebar__group-name",
    "topbar": "pl-topbar",
    "topbar_brand": "pl-topbar__brand",
    "topbar_title": "pl-topbar__title",
    "topbar_actions": "pl-topbar__actions",
    # card
    "card": "pl-card",
    "card_header": "pl-card__header",
    "card_title": "pl-card__title",
    "card_actions": "pl-card__actions",
    "card_body": "pl-card__body",
    # table
    "table_wrap": "pl-table-wrap",
    "table": "pl-table",
    "table_striped": "pl-table--striped",
    "table_compact": "pl-table--compact",
    "table_bordered": "pl-table--bordered",
    "table_numeric": "pl-table__numeric",
    #: Long text that may run onto a second line. Named for what it does, not
    #: for where it sits: `table_wrap` above is the scroll container.
    "table_text_wrap": "pl-table__text-wrap",
    "table_sort": "pl-table__sort",
    "table_sort_active": "is-active",
    "table_empty": "pl-table__empty",
    # pager
    "pager": "pl-pager",
    "pager_status": "pl-pager__status",
    "pager_list": "pl-pager__list",
    "pager_item": "pl-pager__item",
    "pager_link": "pl-pager__link",
    # forms
    "filters": "pl-filters",
    "filters_control": "pl-filters__control",
    "filters_actions": "pl-filters__actions",
    "field": "pl-field",
    "label": "pl-label",
    "input": "pl-input",
    "select": "pl-select",
    "textarea": "pl-textarea",
    "checkbox": "pl-checkbox",
    "help": "pl-help",
    "error": "pl-error",
    # buttons
    "btn": "pl-btn",
    "btn_primary": "pl-btn--primary",
    "btn_danger": "pl-btn--danger",
    "btn_ghost": "pl-btn--ghost",
    "btn_sm": "pl-btn--sm",
    # feedback
    "alert": "pl-alert",
    "alert_info": "pl-alert--info",
    "alert_success": "pl-alert--success",
    "alert_warning": "pl-alert--warning",
    "alert_danger": "pl-alert--danger",
    "tags": "pl-tags",
    "tags_chip": "pl-tags__chip",
    "tags_input": "pl-tags__input",
    "tags_menu": "pl-tags__menu",
    "tags_option": "pl-tags__option",
    "tags_remove": "pl-tags__remove",
    "chip": "pl-chip",
    "chip_success": "pl-chip--success",
    "chip_warning": "pl-chip--warning",
    "chip_danger": "pl-chip--danger",
    "chip_info": "pl-chip--info",
    "chip_neutral": "pl-chip--neutral",
    "muted": "pl-muted",
    "spinner": "pl-spinner",
    "toasts": "pl-toasts",
    # layout
    "grid": "pl-grid",
    "grid_item": "pl-grid__item",
    "stack": "pl-stack",
    "row": "pl-row",
    "spacer": "pl-spacer",
    "slot_empty": "pl-slot--empty",
    "slot_error": "pl-slot--error",
    "visually_hidden": "pl-visually-hidden",
}

#: The pack plinta's own stylesheet is written against.
PLINTA = "plinta"


class StyleError(Exception):
    """A pack was registered twice, named unusably, or names a class that is
    not part of the vocabulary."""


_registry: dict[str, dict[str, str]] = {PLINTA: dict(DEFAULT)}


def register_style_pack(name: str, classes: dict[str, str]) -> dict[str, str]:
    """Register a set of class names for the markup to use.

        register_style_pack("bootstrap5", {
            "btn": "btn btn-secondary",
            "table": "table table-hover",
        })

    Overrides are merged over `DEFAULT`, so a pack lists only what it changes.

    Raises:
        StyleError: the name is taken, is not lowercase ``[a-z][a-z0-9_]*``,
            or a key is not in the vocabulary. An unknown key is refused
            rather than ignored: a misspelled one would silently leave our own
            class in place, which looks like the pack not being installed.
    """
    if not NAME.fullmatch(name):
        raise StyleError(f"{name!r} must be lowercase [a-z][a-z0-9_]*")
    if name in _registry:
        raise StyleError(f"{name!r} is already registered")
    unknown = sorted(set(classes) - set(DEFAULT))
    if unknown:
        raise StyleError(
            f"{name!r} names classes that do not exist: {', '.join(unknown)}"
        )
    _registry[name] = {**DEFAULT, **classes}
    return _registry[name]


def registered() -> list[str]:
    """Every pack, by name."""
    return sorted(_registry)


def classes(name: str | None = None) -> dict[str, str]:
    """The class names in force.

    Reads ``PLINTA_STYLE_PACK`` when no name is given. A pack named by that
    setting but never registered raises rather than falling back: the screens
    would render in plinta's own classes with a stylesheet that does not
    define them, which looks like a broken install rather than a missing app.

    Raises:
        StyleError: nothing is registered under that name.
    """
    from django.conf import settings

    name = name or getattr(settings, "PLINTA_STYLE_PACK", PLINTA) or PLINTA
    try:
        return _registry[name]
    except KeyError:
        known = ", ".join(registered())
        raise StyleError(
            f"no style pack named {name!r} (registered: {known})"
        ) from None

"""The declared relationships between packages, verified at boot.

An app says what it needs on its own `AppConfig`:

    requires = ["plinta.blocks"]              # error if missing
    composes = ["plinta.contrib.labels"]      # structural; error if missing
    enhances = ["plinta.contrib.audit"]       # optional; reported, never fatal

Until this existed the declarations were prose. Every contrib package carried
one and nothing read it, so an install missing `plinta.blocks` failed later,
somewhere else, as an `AttributeError` on a screen.

**Four core layers are not applications.** `utils`, `dates`, `forms` and
`events` are plain packages with no `AppConfig` — importable wherever plinta
is importable, impossible to omit, and so nothing to declare. Naming one is an
error rather than a no-op: a declaration that cannot fail is one a reader
trusts for nothing.
"""
from __future__ import annotations

from django.core.checks import Error, Info, Tags, register

#: Core layers that ship as plain packages. Always importable, never installed.
NON_APP_LAYERS = frozenset(
    {"plinta.utils", "plinta.dates", "plinta.forms", "plinta.events"}
)

CONTRIB = "plinta.contrib."


def installed_names() -> set[str]:
    """Every installed app, by dotted path and by label.

    Both, because a declaration may reasonably use either — `plinta.blocks` is
    the import path and `plinta_blocks` is the label.
    """
    from django.apps import apps

    names = set()
    for config in apps.get_app_configs():
        names.add(config.name)
        names.add(config.label)
    return names


def declared(config, attribute: str) -> tuple[list[str], list[Error]]:
    """One declaration, or the error that it is not a list of strings."""
    value = getattr(config, attribute, None)
    if value is None:
        return [], []
    if isinstance(value, str) or not all(isinstance(v, str) for v in value):
        return [], [
            Error(
                f"{config.label}.{attribute} must be a list of dotted app paths.",
                hint='Write ["plinta.blocks"], not "plinta.blocks".',
                obj=config.label,
                id="plinta.apps.E001",
            )
        ]
    return list(value), []


@register(Tags.compatibility)
def check_declared_dependencies(app_configs=None, **kwargs) -> list:
    """Every `requires`, `composes` and `enhances` names something real.

    `requires` and `composes` are errors when absent — one is a layer the app
    calls into, the other a schema it is bound to, and neither degrades.
    `enhances` is informational: the app is meant to work without it, and the
    message says which feature is asleep rather than that something is wrong.
    """
    from django.apps import apps

    messages: list = []
    installed = installed_names()

    for config in apps.get_app_configs():
        for attribute in ("requires", "composes", "enhances"):
            names, problems = declared(config, attribute)
            messages.extend(problems)
            for name in names:
                messages.extend(
                    _one(config, attribute, name, installed)
                )
    return messages


def _one(config, attribute: str, name: str, installed: set[str]) -> list:
    """Check a single declared name."""
    if name in NON_APP_LAYERS:
        return [
            Error(
                f"{config.label}.{attribute} names {name!r}, which is not an "
                f"application.",
                hint=(
                    f"{name} is a plain package: it is importable wherever "
                    f"plinta is and cannot be missing. Remove it from "
                    f"{attribute}."
                ),
                obj=config.label,
                id="plinta.apps.E002",
            )
        ]

    if name in installed:
        return []

    if attribute == "enhances":
        return [
            Info(
                f"{config.label} enhances {name!r}, which is not installed.",
                hint=(
                    "That is a supported configuration. The feature it adds "
                    "is unavailable and its substitute is in use."
                ),
                obj=config.label,
                id="plinta.apps.I001",
            )
        ]

    kind = "calls into" if attribute == "requires" else "is bound to the schema of"
    return [
        Error(
            f"{config.label} {kind} {name!r}, which is not in INSTALLED_APPS.",
            hint=f'Add "{name}" to INSTALLED_APPS.',
            obj=config.label,
            id="plinta.apps.E003" if attribute == "requires" else "plinta.apps.E004",
        )
    ]


@register(Tags.compatibility)
def check_requires_is_not_sideways(app_configs=None, **kwargs) -> list[Error]:
    """A contrib package does not `require` another contrib package.

    Sideways coupling is legal only as `enhances`, which names a substitute,
    or `composes`, which is structural and cannot degrade. `requires` would
    make a package that is meant to be removable un-removable, silently — the
    trap this whole vocabulary exists to keep open (§2.5).
    """
    from django.apps import apps

    errors = []
    for config in apps.get_app_configs():
        if not config.name.startswith(CONTRIB):
            continue
        names, _ = declared(config, "requires")
        for name in names:
            if name.startswith(CONTRIB):
                errors.append(
                    Error(
                        f"{config.label} requires {name!r}, which is another "
                        f"contrib package.",
                        hint=(
                            "Use enhances, naming what happens without it, or "
                            "composes when the dependency is structural."
                        ),
                        obj=config.label,
                        id="plinta.apps.E005",
                    )
                )
    return errors

"""The declared-dependency checks.

Each test builds a stand-in `AppConfig` rather than installing a real app:
what is under test is the reading of a declaration, and a real app would drag
its models and migrations along for nothing.
"""
from types import SimpleNamespace

import pytest

from plinta.utils.checks import (
    check_declared_dependencies,
    check_requires_is_not_sideways,
    declared,
    installed_names,
)


def config(label="thing", name="yourapp", **declarations):
    return SimpleNamespace(label=label, name=name, **declarations)


@pytest.fixture
def only(monkeypatch):
    """Run the checks over exactly the configs a test supplies."""

    def run(check, *configs):
        from django.apps import apps

        monkeypatch.setattr(apps, "get_app_configs", lambda: list(configs))
        return check()

    return run


# --- requires ---------------------------------------------------------------


def test_a_missing_requirement_is_an_error(only):
    messages = only(
        check_declared_dependencies, config(requires=["plinta.blocks"])
    )
    assert [m.id for m in messages] == ["plinta.apps.E003"]
    assert "not in INSTALLED_APPS" in messages[0].msg
    assert 'Add "plinta.blocks"' in messages[0].hint


def test_an_installed_requirement_is_silent(only):
    """Matched by dotted path or by label, since either is reasonable to write."""
    them = config(label="plinta_blocks", name="plinta.blocks")
    for written in ("plinta.blocks", "plinta_blocks"):
        assert not only(
            check_declared_dependencies, config(requires=[written]), them
        )


def test_declaring_nothing_is_silent(only):
    """Most apps have no relationships, and must not be nagged about it."""
    assert not only(check_declared_dependencies, config())


# --- the four layers that are not apps --------------------------------------


@pytest.mark.parametrize(
    "layer", ["plinta.utils", "plinta.dates", "plinta.forms", "plinta.events"]
)
def test_a_plain_package_may_not_be_required(only, layer):
    """It cannot be missing, so declaring it is a promise that checks nothing.

    Every contrib package shipped `plinta.events` this way, which is what made
    the whole declaration look load-bearing when it was decorative.
    """
    messages = only(check_declared_dependencies, config(requires=[layer]))
    assert [m.id for m in messages] == ["plinta.apps.E002"]
    assert "not an application" in messages[0].msg
    assert "Remove it" in messages[0].hint


# --- enhances ---------------------------------------------------------------


def test_a_missing_enhancement_is_information_not_an_error(only):
    """Absent is a supported configuration — that is what `enhances` means."""
    messages = only(
        check_declared_dependencies, config(enhances=["plinta.contrib.audit"])
    )
    assert [m.id for m in messages] == ["plinta.apps.I001"]
    assert messages[0].level < 30  # below WARNING
    assert "supported configuration" in messages[0].hint


def test_an_installed_enhancement_says_nothing(only):
    them = config(label="plinta_audit", name="plinta.contrib.audit")
    assert not only(
        check_declared_dependencies,
        config(enhances=["plinta.contrib.audit"]),
        them,
    )


# --- composes ---------------------------------------------------------------


def test_a_missing_composition_is_an_error(only):
    """Structural: no substitute exists for a foreign key."""
    messages = only(
        check_declared_dependencies, config(composes=["plinta.contrib.labels"])
    )
    assert [m.id for m in messages] == ["plinta.apps.E004"]
    assert "bound to the schema" in messages[0].msg


# --- shape ------------------------------------------------------------------


def test_a_bare_string_is_caught(only):
    """`requires = "plinta.blocks"` iterates as characters and reports nonsense."""
    messages = only(
        check_declared_dependencies, config(requires="plinta.blocks")
    )
    assert [m.id for m in messages] == ["plinta.apps.E001"]


def test_a_list_of_non_strings_is_caught():
    _, problems = declared(config(requires=[object()]), "requires")
    assert [m.id for m in problems] == ["plinta.apps.E001"]


# --- sideways ---------------------------------------------------------------


def test_contrib_may_not_require_contrib(only):
    """It would make a removable package un-removable, silently (§2.5)."""
    messages = only(
        check_requires_is_not_sideways,
        config(
            label="plinta_comments",
            name="plinta.contrib.comments",
            requires=["plinta.contrib.notifications"],
        ),
    )
    assert [m.id for m in messages] == ["plinta.apps.E005"]
    assert "enhances" in messages[0].hint


def test_contrib_may_require_core(only):
    assert not only(
        check_requires_is_not_sideways,
        config(
            label="plinta_comments",
            name="plinta.contrib.comments",
            requires=["plinta.blocks"],
        ),
    )


def test_a_consumer_app_is_not_policed(only):
    """The rule is about contrib's removability, not about anyone's project."""
    assert not only(
        check_requires_is_not_sideways,
        config(name="catalog", requires=["plinta.contrib.workflow"]),
    )


# --- the real installation --------------------------------------------------


def test_this_installation_declares_only_real_things(db):
    """Runs over what is actually installed, so a shipped typo fails here."""
    assert not [
        m for m in check_declared_dependencies() if m.level >= 30
    ], [m.msg for m in check_declared_dependencies()]


def test_installed_names_carries_both_forms():
    names = installed_names()
    assert "plinta.pages" in names
    assert "plinta_pages" in names

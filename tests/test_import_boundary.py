"""The layer boundary is a test, not a convention.

SPEC §20.3: *a rule enforced by discipline is a rule that lasts until the first
deadline.* Every coupling in the previous design was added by someone who knew
better and was in a hurry, so the rules in §2.3 and §2.5 are checked here
instead:

1. A core layer imports only from layers below it.
2. No core module imports ``plinta.contrib``.
3. A contrib package imports another only where it declares ``enhances`` or
   ``composes`` on its ``AppConfig`` (SPEC §2.5).

Static analysis only — the tree is parsed with ``ast`` and nothing is imported,
so the test runs before the code it guards is installable and cannot be fooled
by an import that only happens at runtime.

Lazy imports count. Moving ``from plinta.blocks import x`` inside a function
hides a violation from a reader but not from this walk, which is exactly how
``components/repeater`` came to import ``blocks`` in v1.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CORE = ROOT / "plinta"
CONTRIB = CORE / "contrib"

# SPEC §2.3. Index is the layer number; a package may import its own layer and
# anything below. `renderers` and `components` are separate layers because the
# second may import the first and never the reverse.
LAYERS: list[tuple[str, ...]] = [
    ("utils", "dates", "forms"),   # 1
    ("events",),                   # 2
    ("permissions",),              # 3
    ("datasources",),              # 4
    ("renderers",),                # 5
    ("components",),               # 6
    ("blocks",),                   # 7
    ("pages",),                    # 8
    ("shell",),                    # 9
]
LAYER_OF = {pkg: i for i, names in enumerate(LAYERS) for pkg in names}


def _modules(root: pathlib.Path) -> list[pathlib.Path]:
    if not root.exists():
        return []
    return [
        p
        for p in root.rglob("*.py")
        if "migrations" not in p.parts and p.name != "__init__.py" or p.name == "__init__.py"
    ]


def _imported_plinta_modules(path: pathlib.Path) -> set[str]:
    """Every ``plinta.*`` module this file imports, at any nesting depth.

    Relative imports are ignored: they cannot cross a package boundary, so they
    cannot violate a layer rule.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names if a.name.startswith("plinta."))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and node.module.startswith("plinta."):
                found.add(node.module)
    return found


def _package_of(module: str) -> str | None:
    """``plinta.permissions.rules`` -> ``permissions``; contrib -> ``None``."""
    parts = module.split(".")
    return parts[1] if len(parts) > 1 and parts[1] != "contrib" else None


def _contrib_package_of(module: str) -> str | None:
    """``plinta.contrib.labels.models`` -> ``labels``; core -> ``None``."""
    parts = module.split(".")
    return parts[2] if len(parts) > 2 and parts[1] == "contrib" else None


def _core_files() -> list[pathlib.Path]:
    return [p for p in _modules(CORE) if CONTRIB not in p.parents and p.parent != CONTRIB]


def test_core_never_imports_contrib():
    """SPEC §2.2, test 3 — core is a closed set."""
    violations = [
        f"{p.relative_to(ROOT)} imports {m}"
        for p in _core_files()
        for m in _imported_plinta_modules(p)
        if m.startswith("plinta.contrib")
    ]
    assert not violations, "core imports contrib:\n  " + "\n  ".join(sorted(violations))


def test_a_layer_imports_only_layers_below_it():
    """SPEC §2.3 — dependencies flow one way."""
    violations = []
    for path in _core_files():
        own = _package_of("plinta." + path.relative_to(CORE).parts[0])
        if own not in LAYER_OF:
            continue
        for module in _imported_plinta_modules(path):
            other = _package_of(module)
            if other is None or other not in LAYER_OF:
                continue
            if LAYER_OF[other] > LAYER_OF[own]:
                violations.append(
                    f"{path.relative_to(ROOT)}: {own} (layer {LAYER_OF[own] + 1}) "
                    f"imports {other} (layer {LAYER_OF[other] + 1})"
                )
    assert not violations, "upward import:\n  " + "\n  ".join(sorted(violations))


def _declared_relationships(package: str) -> set[str]:
    """``enhances`` + ``composes`` off a contrib package's ``AppConfig``.

    Read from the AST rather than by importing, so the check works with the app
    uninstalled. Values are literal lists of dotted paths (SPEC §14.0).
    """
    apps_py = CONTRIB / package / "apps.py"
    if not apps_py.exists():
        return set()
    tree = ast.parse(apps_py.read_text(encoding="utf-8"), filename=str(apps_py))
    declared: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if not names & {"enhances", "composes"}:
            continue
        try:
            for value in ast.literal_eval(node.value):
                declared.add(str(value).split(".")[-1])
        except ValueError:  # not a literal — a computed list is not a declaration
            continue
    return declared


def _contrib_packages() -> list[str]:
    if not CONTRIB.exists():
        return []
    return sorted(p.name for p in CONTRIB.iterdir() if (p / "__init__.py").exists())


def test_contrib_imports_contrib_only_where_declared():
    """SPEC §2.5 — sideways dependency is permitted, undeclared is not."""
    violations = []
    for package in _contrib_packages():
        declared = _declared_relationships(package)
        for path in _modules(CONTRIB / package):
            for module in _imported_plinta_modules(path):
                other = _contrib_package_of(module)
                if other in (None, package) or other in declared:
                    continue
                violations.append(
                    f"{path.relative_to(ROOT)} imports {module}; "
                    f"'{package}' declares no enhances/composes on '{other}'"
                )
    assert not violations, "undeclared sideways import:\n  " + "\n  ".join(sorted(violations))


def test_the_walk_finds_a_planted_violation(tmp_path):
    """The guard's own guard.

    A boundary test that silently matches nothing is worse than none, because it
    reports green. This plants each import form the walk must catch — module
    scope, ``from`` import, and one hidden inside a function — and asserts they
    are seen.
    """
    planted = tmp_path / "planted.py"
    planted.write_text(
        "import plinta.contrib.labels.models\n"
        "from plinta.pages.models import Page\n"
        "def later():\n"
        "    from plinta.blocks.services import render_block\n"
        "    return render_block\n",
        encoding="utf-8",
    )
    assert _imported_plinta_modules(planted) == {
        "plinta.contrib.labels.models",
        "plinta.pages.models",
        "plinta.blocks.services",
    }


@pytest.mark.parametrize(
    ("module", "expected"),
    [
        ("plinta.permissions.rules", "permissions"),
        ("plinta.utils", "utils"),
        ("plinta.contrib.labels.models", None),
    ],
)
def test_package_of(module, expected):
    assert _package_of(module) == expected

"""Check plinta's layer and package boundaries by walking the AST.

Nothing is imported, so lazy imports inside functions are caught too.

Three rules: a core layer imports only layers below it, no core module
imports ``plinta.contrib``, and a contrib package imports another only where
its ``AppConfig`` declares ``enhances`` or ``composes``.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CORE = ROOT / "plinta"
CONTRIB = CORE / "contrib"

# Index = layer number. A package may import its own layer and anything below.
LAYERS: list[tuple[str, ...]] = [
    ("utils", "dates", "forms"),
    ("events",),
    ("permissions",),
    ("datasources",),
    ("renderers",),
    ("components",),
    ("blocks",),
    ("pages",),
    ("shell",),
]
LAYER_OF = {pkg: i for i, names in enumerate(LAYERS) for pkg in names}


def _modules(root: pathlib.Path) -> list[pathlib.Path]:
    if not root.exists():
        return []
    return [p for p in root.rglob("*.py") if "migrations" not in p.parts]


def _imported_plinta_modules(path: pathlib.Path) -> set[str]:
    """Every ``plinta.*`` module imported by this file, at any nesting depth.

    Relative imports are ignored — they cannot cross a package boundary.
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
    return [p for p in _modules(CORE) if CONTRIB not in p.parents]


def _declared_relationships(package: str) -> set[str]:
    """Package names in ``enhances`` / ``composes`` on a contrib ``AppConfig``.

    Read from the AST so the check works with the app uninstalled. A computed
    list is not a declaration and is ignored.
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
        except ValueError:
            continue
    return declared


def _contrib_packages() -> list[str]:
    if not CONTRIB.exists():
        return []
    return sorted(p.name for p in CONTRIB.iterdir() if (p / "__init__.py").exists())


def test_core_never_imports_contrib():
    """Core is a closed set."""
    violations = [
        f"{p.relative_to(ROOT)} imports {m}"
        for p in _core_files()
        for m in _imported_plinta_modules(p)
        if m.startswith("plinta.contrib")
    ]
    assert not violations, "core imports contrib:\n  " + "\n  ".join(sorted(violations))


def test_a_layer_imports_only_layers_below_it():
    """A layer may import downward and sideways within itself, never upward."""
    violations = []
    for path in _core_files():
        own = path.relative_to(CORE).parts[0]
        if own not in LAYER_OF:
            continue
        for module in _imported_plinta_modules(path):
            other = _package_of(module)
            if other not in LAYER_OF:
                continue
            if LAYER_OF[other] > LAYER_OF[own]:
                violations.append(
                    f"{path.relative_to(ROOT)}: {own} (layer {LAYER_OF[own] + 1}) "
                    f"imports {other} (layer {LAYER_OF[other] + 1})"
                )
    assert not violations, "upward import:\n  " + "\n  ".join(sorted(violations))


def test_contrib_imports_contrib_only_where_declared():
    """A sideways import requires ``enhances`` or ``composes`` on the AppConfig."""
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


def test_the_walk_catches_every_import_form(tmp_path):
    """Guard the guard: a walk that matches nothing would report green."""
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

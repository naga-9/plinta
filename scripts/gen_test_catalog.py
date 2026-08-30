#!/usr/bin/env python
"""Generate docs/testing/test-catalog.md from the test suite.

Static analysis only — parses each ``test_*.py`` with ``ast`` and never imports
or runs anything, so it works regardless of test settings / DB / which runner a
suite targets, and can't drift from the code. Each test's description is its
docstring's first line, falling back to a humanised method name.

Run from the repo root (or anywhere — paths are resolved from this file):

    python scripts/gen_test_catalog.py

Regenerate whenever tests are added/renamed/removed (ideally in CI or the docs
build so the published catalog is always current). Do not edit the output by hand.
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "testing" / "test-catalog.md"

# (heading, glob) — order defines the document sections.
SECTIONS = [
    ("plinta package", "plinta/**/test_*.py"),
    ("Standalone suite (tests/)", "tests/test_*.py"),
    ("Example project (integration)", "example/tests/test_*.py"),
]


def humanise(method_name: str) -> str:
    """test_self_copy_raises_valueerror -> 'Self copy raises valueerror'."""
    return method_name[len("test_"):].replace("_", " ").strip().capitalize()


def first_doc_line(node) -> str | None:
    doc = ast.get_docstring(node)
    if not doc:
        return None
    line = doc.strip().splitlines()[0].strip()
    return line or None


def collect(path: pathlib.Path):
    """Yield (class_name_or_None, method_name, description) for each test."""
    tree = ast.parse(path.read_text(encoding="utf-8"))

    def emit(fn, cls):
        if fn.name.startswith("test_"):
            yield cls, fn.name, first_doc_line(fn) or humanise(fn.name)

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield from emit(sub, node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield from emit(node, None)


def main() -> None:
    lines = [
        "# Test catalog",
        "",
        "!!! note",
        "    **Auto-generated** by `scripts/gen_test_catalog.py` from the test",
        "    sources — do not edit by hand. Regenerate with",
        "    `python scripts/gen_test_catalog.py`.",
        "",
    ]

    total = 0
    body = []
    for heading, glob in SECTIONS:
        files = sorted(p for p in ROOT.glob(glob) if "__pycache__" not in p.parts)
        if not files:
            continue
        body.append(f"## {heading}\n")
        for path in files:
            rel = path.relative_to(ROOT).as_posix()
            tests = list(collect(path))
            if not tests:
                continue
            total += len(tests)
            body.append(f"### `{rel}` ({len(tests)})\n")
            for cls, method, desc in tests:
                prefix = f"{cls} › " if cls else ""
                short = method[len("test_"):]
                body.append(f"- **{prefix}{short}** — {desc}")
            body.append("")

    lines.insert(
        7,
        f"_{total} tests across the suite. Names read as their own descriptions; "
        f"the sentence after each is the test's docstring (or a humanised name)._\n",
    )
    lines.extend(body)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT).as_posix()} — {total} tests.")


if __name__ == "__main__":
    main()

"""Generate the plugin manifest from the skills that exist.

Skills live beside the code they document — `plinta/skills/` for core, and
`plinta/contrib/<app>/skills/` for an app that ships its own. Nothing is
copied: the manifest's `skills` field takes directories, so the authored
files *are* what a consumer installs.

    python scripts/build_plugin.py            # write the manifest
    python scripts/build_plugin.py --check    # fail if it is out of date

`--check` runs in CI. Without it the manifest drifts the first time somebody
adds a skill directory and forgets, which is the whole failure this generator
exists to prevent.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".claude-plugin" / "plugin.json"

PLUGIN = {
    "name": "plinta",
    "displayName": "plinta",
    "description": (
        "Skills for extending plinta — components, renderers, policies, "
        "capabilities, and the contrib apps that are installed."
    ),
    "homepage": "https://plinta.readthedocs.io/",
    "repository": "https://github.com/naga-9/plinta",
    "license": "MIT",
    "keywords": ["django", "dashboard", "permissions", "plinta"],
}


def skill_dirs() -> list[str]:
    """Every directory holding `<name>/SKILL.md`, core first then contrib.

    Discovered rather than listed, so a new contrib app's skills are picked up
    by regenerating instead of by remembering.
    """
    found = {
        skill.parent.parent for skill in ROOT.glob("plinta/**/skills/*/SKILL.md")
    }
    return sorted(f"./{d.relative_to(ROOT).as_posix()}/" for d in found)


def build() -> dict:
    return {**PLUGIN, "version": version(), "skills": skill_dirs()}


def version() -> str:
    """The version in `pyproject.toml`, so the plugin and the wheel agree."""
    import tomllib

    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the manifest is not what this would write",
    )
    args = parser.parse_args()

    wanted = json.dumps(build(), indent=2, ensure_ascii=False) + "\n"

    if args.check:
        current = MANIFEST.read_text(encoding="utf-8") if MANIFEST.exists() else ""
        if current == wanted:
            return 0
        print(
            f"{MANIFEST.relative_to(ROOT)} is out of date.\n"
            "Run: python scripts/build_plugin.py",
            file=sys.stderr,
        )
        return 1

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(wanted, encoding="utf-8")
    print(f"wrote {MANIFEST.relative_to(ROOT)} ({len(build()['skills'])} directories)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

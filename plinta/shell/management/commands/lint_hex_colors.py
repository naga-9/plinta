"""Refuse a raw colour anywhere but the token file.

One hardcoded colour breaks dark mode in a way nobody notices until someone
switches, which is why this runs in CI rather than being a convention.
"""
import pathlib
import re

from django.core.management.base import BaseCommand, CommandError

from plinta.shell import tokens

#: Where a colour may legitimately appear.
ALLOWED = {"tokens.json", "tokens.css"}

#: Checked for raw colours: everything the shell serves.
SUFFIXES = {".css", ".js", ".html"}

HEX = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?(?:[0-9a-fA-F]{2})?\b")

#: A colour function. Only a literal one offends: `rgb(var(--pl-accent-rgb) /
#: 0.1)` is a token used exactly as intended, and is why the rgb companions
#: exist at all.
FUNCTION = re.compile(r"\b(?:rgba?|hsla?|oklch|oklab|lab|lch|color)\([^)]*\)")


def offenders(root: pathlib.Path) -> list[str]:
    """Every raw colour outside the token file, as ``path:line: text``.

    Both spellings, because catching only hex would let `rgb(0 0 0 / 0.4)`
    through — a colour that is just as blind to the theme.
    """
    found = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in SUFFIXES or path.name in ALLOWED:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in HEX.finditer(line):
                found.append(f"{path}:{number}: {match.group(0)}")
            for match in FUNCTION.finditer(line):
                if "var(" not in match.group(0):
                    found.append(f"{path}:{number}: {match.group(0)}")
    return found


class Command(BaseCommand):
    help = "Fail if a raw colour appears outside design/tokens.json."

    def handle(self, *args, **options):
        found = offenders(pathlib.Path(tokens.DESIGN).parent)
        if found:
            raise CommandError(
                "raw colours outside tokens.json:\n  " + "\n  ".join(found)
            )
        self.stdout.write("no raw colours outside tokens.json")

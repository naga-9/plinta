"""Regenerate tokens.css and tokens.js from design/tokens.json."""
from django.core.management.base import BaseCommand, CommandError

from plinta.shell import tokens


class Command(BaseCommand):
    help = "Generate static/plinta/css/tokens.css and js/tokens.js from tokens.json."

    def handle(self, *args, **options):
        try:
            css, js = tokens.write()
        except tokens.TokenError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"wrote {css}")
        self.stdout.write(f"wrote {js}")

"""
Fill missing Shoe.insole_length_in / insole_width_in with placeholder inches so the
recommendations API can compute fit scores (otherwise every row is UNSCORED).

Run only on development databases. Real catalog data should use measured insoles.
"""

from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from backend.models import Shoe

# Generic mid-size insole (inches); enough for the scorer to run — replace with real data later.
DEFAULT_LENGTH = Decimal("10.500")
DEFAULT_WIDTH = Decimal("3.650")


class Command(BaseCommand):
    help = "Backfill missing insole dimensions so fit scores appear (dev)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Run even when DEBUG is False (only on a disposable dev DB).",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(
                self.style.ERROR(
                    "Refusing: set DJANGO_DEBUG=1 in .env or pass --force for a dev database."
                )
            )
            return

        qs = Shoe.objects.filter(
            Q(insole_length_in__isnull=True) | Q(insole_width_in__isnull=True)
        )
        n = qs.count()
        if n == 0:
            self.stdout.write(self.style.SUCCESS("No shoes missing insole dimensions."))
            return

        updated = 0
        for shoe in qs.iterator():
            changed = False
            if shoe.insole_length_in is None:
                shoe.insole_length_in = DEFAULT_LENGTH
                changed = True
            if shoe.insole_width_in is None:
                shoe.insole_width_in = DEFAULT_WIDTH
                changed = True
            if changed:
                shoe.save(update_fields=["insole_length_in", "insole_width_in"])
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {updated} shoe(s) with placeholder insole dimensions "
                f'({DEFAULT_LENGTH}" x {DEFAULT_WIDTH}").'
            )
        )

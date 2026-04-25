"""
Management command: export a work queue of shoes for the browser-based sync routine.

Outputs one JSON record per shoe containing the measured sizes and any existing
GOAT URLs already stored in the DB. Feed this file into the /sync-shoes slash
command, which does the actual browser scraping.

Usage:
    # Export all eligible shoes
    python manage.py export_shoes_for_sync --output queue.json

    # Single shoe (for testing)
    python manage.py export_shoes_for_sync --shoe-id 12 --output queue.json

    # Only shoes that have a specific measured size
    python manage.py export_shoes_for_sync --size 10.5 --output queue.json

Eligibility rules:
    1. Active shoes that have at least one insole-measured ShoeSize.
    2. Inactive shoes that have never been synced, or were last synced > 30 days
       ago — so discontinued shoes get periodically retried in case they came
       back into production.
"""

import json
import sys
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from backend.models import Shoe, ShoeColorway


RETRY_INACTIVE_AFTER_DAYS = 30


class Command(BaseCommand):
    help = "Export a browser-sync work queue of shoes with insole measurements."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            metavar="FILE",
            help="Write queue JSON to this file. Omit to print to stdout.",
        )
        parser.add_argument(
            "--shoe-id",
            type=int,
            metavar="ID",
            help="Export only this shoe (DB pk). Useful for testing a single shoe.",
        )
        parser.add_argument(
            "--size",
            type=float,
            metavar="SIZE",
            help="Only include shoes that have this US size as a measured insole size.",
        )
        parser.add_argument(
            "--include-recently-synced",
            action="store_true",
            default=False,
            help="Include active shoes even if synced within the last 6 days (default: skip them).",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        retry_cutoff = now - timedelta(days=RETRY_INACTIVE_AFTER_DAYS)
        fresh_cutoff = now - timedelta(days=6)

        # Base filter: must have at least one insole-measured ShoeSize
        insole_q = Q(sizes__insole_length_in__isnull=False)

        if options["shoe_id"]:
            shoes_qs = (
                Shoe.objects
                .prefetch_related("sizes", "colorways")
                .filter(insole_q, pk=options["shoe_id"])
                .distinct()
            )
        else:
            active_q = Q(is_active=True)
            inactive_retry_q = Q(is_active=False) & (
                Q(last_synced_at__isnull=True) |
                Q(last_synced_at__lt=retry_cutoff)
            )

            shoes_qs = (
                Shoe.objects
                .prefetch_related("sizes", "colorways")
                .filter(insole_q)
                .filter(active_q | inactive_retry_q)
                .distinct()
            )

            # Skip shoes synced very recently unless --include-recently-synced
            if not options["include_recently_synced"]:
                shoes_qs = shoes_qs.exclude(
                    is_active=True,
                    last_synced_at__gte=fresh_cutoff,
                )

        shoes = list(shoes_qs)

        if not shoes:
            self.stderr.write("No eligible shoes found. Nothing to export.")
            sys.exit(0)

        queue = []

        for shoe in shoes:
            # Collect insole-measured US sizes for this shoe
            measured_sizes = sorted(
                float(s.us_size)
                for s in shoe.sizes.all()
                if s.insole_length_in is not None
            )

            # Apply --size filter after loading (simpler than adding to query)
            if options["size"] and options["size"] not in measured_sizes:
                continue

            if not measured_sizes:
                continue

            # Gather existing GOAT colorway URLs — gives the slash command a
            # direct link to start from instead of having to search from scratch.
            existing_colorways = [
                {
                    "goat_id": cw.goat_id,
                    "name": cw.name,
                    "product_url": cw.product_url,
                    "last_synced_at": cw.last_synced_at.isoformat() if cw.last_synced_at else None,
                }
                for cw in shoe.colorways.all()
                if cw.product_url
            ]

            # Best existing GOAT URL: most recently synced colorway's product page.
            # The slash command uses this to land directly on the shoe's GOAT page
            # and enumerate all colorways from there.
            best_goat_url = None
            if existing_colorways:
                synced = [c for c in existing_colorways if c["last_synced_at"]]
                if synced:
                    best_goat_url = max(synced, key=lambda c: c["last_synced_at"])["product_url"]
                else:
                    best_goat_url = existing_colorways[0]["product_url"]

            queue.append({
                "shoe_id": shoe.pk,
                "brand": shoe.brand,
                "model": shoe.model,
                "sku": shoe.sku,
                "measured_sizes": measured_sizes,
                "is_currently_active": shoe.is_active,
                "last_synced_at": shoe.last_synced_at.isoformat() if shoe.last_synced_at else None,
                "existing_goat_url": best_goat_url,
                "existing_colorway_count": len(existing_colorways),
            })

        if not queue:
            self.stderr.write("No shoes matched all filters. Nothing to export.")
            sys.exit(0)

        output = json.dumps(queue, indent=2)

        if options["output"]:
            with open(options["output"], "w", encoding="utf-8") as f:
                f.write(output)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Exported {len(queue)} shoe(s) to {options['output']}"
                )
            )
            # Print a quick summary to stdout so the user knows what's coming
            active_count = sum(1 for s in queue if s["is_currently_active"])
            retry_count = len(queue) - active_count
            self.stdout.write(f"  Active shoes:            {active_count}")
            self.stdout.write(f"  Inactive (retry):        {retry_count}")
            self.stdout.write(f"  With existing GOAT URLs: {sum(1 for s in queue if s['existing_goat_url'])}")
            self.stdout.write(f"  Cold searches needed:    {sum(1 for s in queue if not s['existing_goat_url'])}")
        else:
            self.stdout.write(output)

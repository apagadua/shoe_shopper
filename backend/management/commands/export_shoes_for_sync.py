"""
Management command: export a work queue of shoes for the browser-based sync routine.

Outputs one JSON record per shoe containing the measured sizes, the scraping
method (pullmd or chrome), and any existing colorway URLs already stored in
the DB. Feed this file into the /sync-shoes slash command.

GOAT-managed shoes are automatically excluded — they are handled by seed_kicks.
A shoe is considered GOAT-managed if:
  • shoe.kicks_id is not null, OR
  • all of its existing colorways have native GOAT slugs (e.g. "550-white-grey-bb550pb1")

Method routing:
  • chrome — nike.com, ebay.com, vivobarefoot.com, converse.com
  • pullmd — everything else (hoka.com, amazon.com, newbalance.com, zappos.com, etc.)

Usage:
    # Export all eligible non-GOAT shoes
    python manage.py export_shoes_for_sync --output queue.json

    # Single shoe (for testing)
    python manage.py export_shoes_for_sync --shoe-id 12 --output queue.json

    # Include shoes synced within the last 6 days (force re-sync)
    python manage.py export_shoes_for_sync --include-recently-synced --output queue.json

    # Include GOAT shoes in the output (rare — for debugging)
    python manage.py export_shoes_for_sync --include-goat --output queue.json

Eligibility rules (for non-GOAT shoes):
    1. Active shoes that have at least one insole-measured ShoeSize.
    2. Inactive shoes that have never been synced, or were last synced > 30 days
       ago — so discontinued shoes get periodically retried in case they restocked.
"""

import json
import re
import sys
from datetime import timedelta
from urllib.parse import urlparse

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from backend.models import Shoe, ShoeColorway


RETRY_INACTIVE_AFTER_DAYS = 30

# Domains that require Chrome browser automation rather than pullmd
CHROME_DOMAINS = {
    'nike.com',
    'ebay.com',
    'vivobarefoot.com',
    'converse.com',
}

# Native GOAT slug pattern: lowercase alphanumeric + hyphens only, no underscore prefix
# Examples: "550-white-grey-bb550pb1", "air-max-90-white-cn8490-100"
GOAT_SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]*$')


def _classify_url(url):
    """Return 'chrome' if the URL domain needs browser automation, else 'pullmd'."""
    if not url:
        return 'pullmd'
    try:
        hostname = urlparse(url).hostname or ''
        if hostname.startswith('www.'):
            hostname = hostname[4:]
        if hostname in CHROME_DOMAINS:
            return 'chrome'
    except Exception:
        pass
    return 'pullmd'


def _is_goat_managed(shoe, colorways):
    """
    True if this shoe's data should come from seed_kicks (not the browser sync).

    Criteria (either is sufficient):
      • shoe.kicks_id is set — authoritative GOAT marker from initial seeding
      • All existing colorways have native GOAT slugs (no underscore prefix)
    """
    if shoe.kicks_id:
        return True
    if not colorways:
        return False
    return all(
        cw.goat_id and GOAT_SLUG_RE.match(cw.goat_id)
        for cw in colorways
    )


class Command(BaseCommand):
    help = "Export a browser-sync work queue of non-GOAT shoes with insole measurements."

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
        parser.add_argument(
            "--include-goat",
            action="store_true",
            default=False,
            help="Include GOAT-managed shoes in the output (normally handled by seed_kicks).",
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
        goat_skipped = 0

        for shoe in shoes:
            colorways = list(shoe.colorways.all())

            # Skip GOAT-managed shoes unless --include-goat is set
            if not options["include_goat"] and _is_goat_managed(shoe, colorways):
                goat_skipped += 1
                continue

            # Collect insole-measured US sizes for this shoe
            measured_sizes = sorted(
                float(s.us_size)
                for s in shoe.sizes.all()
                if s.insole_length_in is not None
            )

            # Apply --size filter
            if options["size"] and options["size"] not in measured_sizes:
                continue

            if not measured_sizes:
                continue

            # Determine scraping method from the best available URL
            if colorways:
                representative_url = colorways[0].product_url or shoe.product_url
            else:
                representative_url = shoe.product_url

            method = _classify_url(representative_url)

            # Build the existing colorways list — gives the sync command direct URLs
            # to visit instead of guessing. Includes all colorways with a product_url.
            existing_colorways = [
                {
                    "id": cw.pk,
                    "goat_id": cw.goat_id,
                    "name": cw.name,
                    "sku": cw.sku,
                    "product_url": cw.product_url,
                    "image_url": cw.image_url,
                    "last_synced_at": cw.last_synced_at.isoformat() if cw.last_synced_at else None,
                }
                for cw in colorways
                if cw.product_url
            ]

            # Non-GOAT retailer URL stored on the shoe itself (e.g. eBay, Hoka, Amazon).
            # Present for shoes without colorways or as the canonical landing page.
            known_retailer_url = None
            if shoe.product_url and "goat.com" not in (shoe.product_url or ""):
                known_retailer_url = shoe.product_url

            queue.append({
                "shoe_id": shoe.pk,
                "brand": shoe.brand,
                "model": shoe.model,
                "sku": shoe.sku,
                "gender": shoe.gender,
                "measured_sizes": measured_sizes,
                "is_currently_active": shoe.is_active,
                "last_synced_at": shoe.last_synced_at.isoformat() if shoe.last_synced_at else None,
                "method": method,
                "known_retailer_url": known_retailer_url,
                "existing_colorways": existing_colorways,
            })

        if not queue:
            self.stderr.write(
                f"No non-GOAT shoes matched all filters. "
                f"({goat_skipped} GOAT shoes were skipped — run seed_kicks for those.)"
            )
            sys.exit(0)

        output = json.dumps(queue, indent=2)

        if options["output"]:
            with open(options["output"], "w", encoding="utf-8") as f:
                f.write(output)

            chrome_count = sum(1 for s in queue if s["method"] == "chrome")
            pullmd_count = sum(1 for s in queue if s["method"] == "pullmd")
            active_count = sum(1 for s in queue if s["is_currently_active"])
            retry_count = len(queue) - active_count

            self.stdout.write(
                self.style.SUCCESS(f"Exported {len(queue)} shoe(s) to {options['output']}")
            )
            self.stdout.write(f"  method=chrome:             {chrome_count}")
            self.stdout.write(f"  method=pullmd:             {pullmd_count}")
            self.stdout.write(f"  Active shoes:              {active_count}")
            self.stdout.write(f"  Inactive (retry):          {retry_count}")
            self.stdout.write(f"  With known retailer URL:   {sum(1 for s in queue if s['known_retailer_url'])}")
            self.stdout.write(f"  With existing colorways:   {sum(1 for s in queue if s['existing_colorways'])}")
            self.stdout.write(f"  Cold searches needed:      {sum(1 for s in queue if not s['known_retailer_url'] and not s['existing_colorways'])}")
            if goat_skipped:
                self.stdout.write(f"  GOAT shoes skipped:        {goat_skipped} (run: python manage.py seed_kicks)")
        else:
            self.stdout.write(output)

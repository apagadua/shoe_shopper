"""
Management command: apply browser-scraped shoe data to the database.

Reads the payload JSON produced by the /sync-shoes slash command and upserts
ShoeColorway + ShoeColorwaySize records, then sets Shoe.is_active accordingly.

Usage:
    # Dry run — preview what would change
    python manage.py apply_shoe_sync --input payload.json --dry-run

    # Apply to DB
    python manage.py apply_shoe_sync --input payload.json

    # Apply only one shoe from the payload (for testing)
    python manage.py apply_shoe_sync --input payload.json --shoe-id 12

Payload record statuses:
    "found_goat"      — found on GOAT; colorways have real goat_ids
    "found_retailer"  — found on a non-GOAT retailer; goat_ids are synthetic
    "discontinued"    — only on eBay/resale or not found anywhere; mark inactive
    "error"           — browser hit an error; skip, leave is_active unchanged
"""

import json
import os
import sys

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from backend.models import Shoe, ShoeColorway, ShoeColorwaySize


ACTIVE_STATUSES = {"found_goat", "found_retailer"}
DISCONTINUED_STATUSES = {"discontinued"}
SKIP_STATUSES = {"error"}


class Command(BaseCommand):
    help = "Apply browser-scraped shoe sync payload to the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            metavar="FILE",
            required=True,
            help="Path to the payload JSON file produced by /sync-shoes.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview changes without writing to the database.",
        )
        parser.add_argument(
            "--shoe-id",
            type=int,
            metavar="ID",
            help="Apply only this shoe's record from the payload.",
        )

    def handle(self, *args, **options):
        input_file = options["input"]
        dry_run = options["dry_run"]
        filter_shoe_id = options.get("shoe_id")

        if not os.path.exists(input_file):
            raise CommandError(f"File not found: {input_file}")

        with open(input_file, "r", encoding="utf-8") as f:
            payload = json.load(f)

        if not isinstance(payload, list):
            raise CommandError("Payload must be a JSON array.")

        if filter_shoe_id:
            payload = [r for r in payload if r.get("shoe_id") == filter_shoe_id]
            if not payload:
                raise CommandError(f"No record for shoe_id={filter_shoe_id} in payload.")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no database writes.\n"))

        run_started = timezone.now()

        stats = {
            "activated": 0,
            "deactivated": 0,
            "colorways_upserted": 0,
            "sizes_upserted": 0,
            "skipped_error": 0,
            "skipped_missing": 0,
        }

        for record in payload:
            self._apply_record(record, dry_run, run_started, stats)

        self.stdout.write(
            self.style.SUCCESS("\nDone" + (" (dry run)" if dry_run else "") + ".")
        )
        self.stdout.write(f"  Shoes activated:    {stats['activated']}")
        self.stdout.write(f"  Shoes deactivated:  {stats['deactivated']}")
        self.stdout.write(f"  Colorways upserted: {stats['colorways_upserted']}")
        self.stdout.write(f"  Sizes upserted:     {stats['sizes_upserted']}")
        self.stdout.write(f"  Skipped (error):    {stats['skipped_error']}")
        self.stdout.write(f"  Skipped (missing):  {stats['skipped_missing']}")

    # ------------------------------------------------------------------

    def _apply_record(self, record, dry_run, run_started, stats):
        shoe_id = record.get("shoe_id")
        status = record.get("status", "error")
        colorways = record.get("colorways", [])
        source = record.get("source", "unknown")
        source_url = record.get("source_url")
        notes = record.get("notes", "")

        try:
            shoe = Shoe.objects.prefetch_related("sizes").get(pk=shoe_id)
        except Shoe.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"  Shoe pk={shoe_id} not found — skipping"))
            stats["skipped_missing"] += 1
            return

        label = f"{shoe.brand} {shoe.model} (pk={shoe_id})"

        if status in SKIP_STATUSES:
            self.stdout.write(self.style.WARNING(f"  SKIP  {label} — status=error: {notes}"))
            stats["skipped_error"] += 1
            return

        if status in DISCONTINUED_STATUSES:
            self.stdout.write(self.style.WARNING(f"  INACT {label} — discontinued: {notes}"))
            if not dry_run:
                Shoe.objects.filter(pk=shoe_id).update(
                    is_active=False,
                    last_synced_at=run_started,
                )
            stats["deactivated"] += 1
            return

        if status not in ACTIVE_STATUSES:
            self.stderr.write(self.style.ERROR(
                f"  Unknown status '{status}' for shoe pk={shoe_id} — skipping"
            ))
            stats["skipped_error"] += 1
            return

        # status is found_goat or found_retailer
        if not colorways:
            # Payload says active but has no colorways — treat as discontinued
            self.stdout.write(self.style.WARNING(
                f"  INACT {label} — {status} but no colorways in payload"
            ))
            if not dry_run:
                Shoe.objects.filter(pk=shoe_id).update(
                    is_active=False,
                    last_synced_at=run_started,
                )
            stats["deactivated"] += 1
            return

        insole_sizes = set(
            float(s.us_size)
            for s in shoe.sizes.all()
            if s.insole_length_in is not None
        )

        colorways_written = 0
        sizes_written = 0

        for cw in colorways:
            goat_id = cw.get("goat_id")
            if not goat_id:
                self.stderr.write(self.style.ERROR(
                    f"    Colorway missing goat_id for shoe pk={shoe_id} — skipping colorway"
                ))
                continue

            cw_name = cw.get("name", "Unknown")
            image_url = cw.get("image_url")
            product_url = cw.get("product_url")
            size_rows = cw.get("sizes", [])

            available_in_our_sizes = [
                s for s in size_rows
                if float(s["us_size"]) in insole_sizes and s.get("is_available")
            ]

            self.stdout.write(
                f"  {'[DRY] ' if dry_run else ''}"
                f"{'GOAT' if status == 'found_goat' else source[:12]:12s} "
                f"{label} / {cw_name} "
                f"— {len(available_in_our_sizes)} avail in our sizes"
            )

            if not dry_run:
                n_sizes = self._write_colorway(
                    shoe, goat_id, cw_name, image_url, product_url,
                    size_rows, insole_sizes,
                )
                sizes_written += n_sizes

            colorways_written += 1

        # Mark sizes from colorways NOT in this payload as unavailable.
        # Any ShoeColorwaySize whose parent colorway wasn't touched this run
        # (last_synced_at < run_started) is stale.
        if not dry_run:
            stale_qs = ShoeColorwaySize.objects.filter(
                colorway__shoe=shoe,
                colorway__last_synced_at__lt=run_started,
            )
            stale_count = stale_qs.update(is_available=False)
            if stale_count:
                self.stdout.write(
                    self.style.WARNING(f"    Marked {stale_count} stale size(s) unavailable")
                )

            # Build shoe-level update fields
            shoe_update = {
                "is_active": True,
                "product_url": source_url or shoe.product_url,
                "last_synced_at": run_started,
            }

            # shoe_image_url: accept explicit value from payload (used for eBay and
            # other single-listing shoes that don't derive their image from a colorway).
            # For multi-colorway shoes, the frontend derives the display image from
            # ShoeColorway.image_url, so we leave shoe_image_url unchanged unless
            # the payload explicitly provides it.
            explicit_image = record.get("shoe_image_url")
            if explicit_image:
                shoe_update["shoe_image_url"] = explicit_image

            Shoe.objects.filter(pk=shoe_id).update(**shoe_update)

        stats["activated"] += 1
        stats["colorways_upserted"] += colorways_written
        stats["sizes_upserted"] += sizes_written

    # ------------------------------------------------------------------

    def _write_colorway(self, shoe, goat_id, name, image_url, product_url, size_rows, insole_sizes):
        sizes_written = 0
        with transaction.atomic():
            colorway, _ = ShoeColorway.objects.update_or_create(
                goat_id=goat_id,
                defaults={
                    "shoe": shoe,
                    "name": name,
                    "image_url": image_url,
                    "product_url": product_url,
                    "last_synced_at": timezone.now(),
                },
            )

            seen_sizes = set()
            for size_row in size_rows:
                try:
                    us_size = float(size_row["us_size"])
                except (KeyError, TypeError, ValueError):
                    continue

                if us_size not in insole_sizes:
                    continue

                ShoeColorwaySize.objects.update_or_create(
                    colorway=colorway,
                    us_size=us_size,
                    defaults={
                        "price_usd": size_row.get("price_usd"),
                        "is_available": bool(size_row.get("is_available", False)),
                    },
                )
                seen_sizes.add(us_size)
                sizes_written += 1

            # Any of our measured sizes not returned by the scraper → unavailable
            for missing in (insole_sizes - seen_sizes):
                ShoeColorwaySize.objects.update_or_create(
                    colorway=colorway,
                    us_size=missing,
                    defaults={"is_available": False, "price_usd": None},
                )

        return sizes_written

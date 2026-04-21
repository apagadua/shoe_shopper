"""
Management command: sync GOAT colorway and per-size pricing data into the DB.

For every Shoe that has at least one insole-measured ShoeSize:
  1. Search GOAT for "{brand} {model}" (paginated, up to 3 pages / 300 results).
  2. For each brand-matching result, fetch the product detail to get per-size variants.
  3. Upsert ShoeColorway (on goat_id) and ShoeColorwaySize (on colorway + us_size).
  4. Mark stale colorway sizes unavailable (colorways not seen in this run).
  5. Set Shoe.is_active = True if at least one colorway was synced, False if search
     returned nothing.  API errors during search leave is_active unchanged.

Usage:
    python manage.py seed_kicks
    python manage.py seed_kicks --dry-run
"""

import os
import time

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from backend.models import Shoe, ShoeColorway, ShoeColorwaySize

KICKS_API_BASE = "https://api.kicks.dev/v3"
MAX_PAGES = 3       # cap at 300 results per shoe
PAGE_LIMIT = 100    # GOAT API max per page
SLEEP_BETWEEN = 0.1  # seconds between requests


def _auth_header(api_key):
    return api_key if api_key.startswith("Bearer ") else f"Bearer {api_key}"


def _colorway_name(product):
    """Prefer short marketing name, fall back to colorway string, then full name."""
    return (
        product.get("nickname")
        or product.get("colorway")
        or product.get("name")
        or "Unknown"
    )


class Command(BaseCommand):
    help = "Sync GOAT colorway and per-size pricing data for all shoes with insole measurements."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview what would happen without writing to the database.",
        )

    def handle(self, *args, **options):
        api_key = os.environ.get("KICKS_API_KEY")
        if not api_key:
            raise CommandError("KICKS_API_KEY is not set. Add it to your .env file.")

        auth = _auth_header(api_key)
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no database writes.\n"))

        run_started = timezone.now()

        # Only process shoes that have at least one insole-measured size
        shoes = list(
            Shoe.objects.prefetch_related("sizes")
            .filter(sizes__insole_length_in__isnull=False)
            .distinct()
        )

        if not shoes:
            self.stdout.write("No shoes with insole measurements found. Nothing to sync.")
            return

        self.stdout.write(f"Syncing {len(shoes)} shoes from GOAT...\n")

        total_colorways = 0
        total_sizes = 0
        skipped = 0

        for shoe in shoes:
            insole_sizes = set(
                float(s.us_size)
                for s in shoe.sizes.all()
                if s.insole_length_in is not None
            )

            result = self._sync_shoe(shoe, insole_sizes, auth, dry_run, run_started)
            if result is None:
                skipped += 1
            else:
                c, s = result
                total_colorways += c
                total_sizes += s

            time.sleep(SLEEP_BETWEEN)

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Colorways upserted: {total_colorways}  "
            f"Sizes upserted: {total_sizes}  "
            f"Shoes with no match: {skipped}"
            + (" (dry run)" if dry_run else "")
        ))

    def _sync_shoe(self, shoe, insole_sizes, auth, dry_run, run_started):
        """
        Sync one shoe. Returns (colorways_upserted, sizes_upserted) or None on skip.
        """
        query = f"{shoe.brand} {shoe.model}"
        self.stdout.write(f"  {shoe.brand} {shoe.model}...")

        # --- Step 1: Search with pagination (up to MAX_PAGES) ---
        search_results = []
        try:
            for page in range(1, MAX_PAGES + 1):
                resp = requests.get(
                    f"{KICKS_API_BASE}/goat/products",
                    params={"query": query, "limit": PAGE_LIMIT, "page": page},
                    headers={"Authorization": auth},
                    timeout=30,
                )
                resp.raise_for_status()
                body = resp.json()
                data = body.get("data") or []
                meta = body.get("meta") or {}

                # Filter to brand-matching products
                for product in data:
                    api_brand = (product.get("brand") or "").lower()
                    if shoe.brand.lower() in api_brand or api_brand in shoe.brand.lower():
                        search_results.append(product)

                # Check if more pages exist
                current_page = meta.get("current_page", page)
                per_page = meta.get("per_page", PAGE_LIMIT)
                total = meta.get("total", 0)
                if current_page * per_page >= total:
                    break

                time.sleep(SLEEP_BETWEEN)

        except requests.RequestException as exc:
            self.stderr.write(self.style.ERROR(
                f"    [SEARCH ERROR] {shoe.brand} {shoe.model}: {exc} — skipping, is_active unchanged"
            ))
            return None

        if not search_results:
            self.stdout.write(self.style.WARNING(f"    No GOAT results — marking inactive"))
            if not dry_run:
                Shoe.objects.filter(pk=shoe.pk).update(is_active=False, last_synced_at=timezone.now())
            return None

        # --- Step 2: Detail fetch for each colorway ---
        colorways_upserted = 0
        sizes_upserted = 0

        for product in search_results:
            slug = product.get("slug")
            if not slug:
                continue

            try:
                detail_resp = requests.get(
                    f"{KICKS_API_BASE}/goat/products/{slug}",
                    headers={"Authorization": auth},
                    timeout=30,
                )
                detail_resp.raise_for_status()
                detail = detail_resp.json()
                time.sleep(SLEEP_BETWEEN)
            except requests.RequestException as exc:
                self.stderr.write(self.style.ERROR(
                    f"    [DETAIL ERROR] slug={slug}: {exc} — skipping colorway"
                ))
                time.sleep(SLEEP_BETWEEN)
                continue

            goat_id = str(detail.get("id") or product.get("id") or "")
            if not goat_id:
                continue

            name = _colorway_name(detail)
            image_url = detail.get("image_url") or None
            product_url = detail.get("link") or None
            sku = detail.get("sku") or None

            self.stdout.write(
                f"    {'[DRY] ' if dry_run else ''}colorway: {name}"
                f" (goat_id={goat_id})"
            )

            if dry_run:
                colorways_upserted += 1
                # Count what sizes would be written
                for variant in (detail.get("variants") or []):
                    if variant.get("market") != "US" or variant.get("currency") != "USD":
                        continue
                    try:
                        us_size = float(variant["size"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if not (1.0 <= us_size <= 20.0):
                        continue
                    if us_size not in insole_sizes:
                        continue
                    sizes_upserted += 1
                continue

            with transaction.atomic():
                colorway, _ = ShoeColorway.objects.update_or_create(
                    goat_id=goat_id,
                    defaults={
                        "shoe": shoe,
                        "sku": sku,
                        "name": name,
                        "image_url": image_url,
                        "product_url": product_url,
                        "last_synced_at": timezone.now(),
                    },
                )
                colorways_upserted += 1

                # --- Step 3: Upsert per-size data ---
                variant_sizes_seen = set()
                for variant in (detail.get("variants") or []):
                    if variant.get("market") != "US" or variant.get("currency") != "USD":
                        continue
                    try:
                        us_size = float(variant["size"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if not (1.0 <= us_size <= 20.0):
                        continue
                    if us_size not in insole_sizes:
                        continue

                    lowest_ask = variant.get("lowest_ask")
                    price = lowest_ask if lowest_ask else None
                    is_available = bool(variant.get("available", False))

                    ShoeColorwaySize.objects.update_or_create(
                        colorway=colorway,
                        us_size=us_size,
                        defaults={
                            "price_usd": price,
                            "is_available": is_available,
                        },
                    )
                    variant_sizes_seen.add(us_size)
                    sizes_upserted += 1

                # Mark insole-measured sizes absent from GOAT variants as unavailable
                for missing_size in insole_sizes - variant_sizes_seen:
                    ShoeColorwaySize.objects.update_or_create(
                        colorway=colorway,
                        us_size=missing_size,
                        defaults={"is_available": False, "price_usd": None},
                    )

        # --- Step 4: Mark stale colorways unavailable ---
        if not dry_run:
            stale_qs = ShoeColorwaySize.objects.filter(
                colorway__shoe=shoe,
                colorway__last_synced_at__lt=run_started,
            )
            stale_count = stale_qs.update(is_available=False)
            if stale_count:
                self.stdout.write(
                    self.style.WARNING(f"    Marked {stale_count} stale sizes unavailable")
                )

            # --- Step 5: Update Shoe.is_active ---
            Shoe.objects.filter(pk=shoe.pk).update(
                is_active=(colorways_upserted > 0),
                last_synced_at=timezone.now(),
            )

        self.stdout.write(
            f"    {colorways_upserted} colorways, {sizes_upserted} sizes"
        )
        return colorways_upserted, sizes_upserted

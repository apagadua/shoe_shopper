"""
Management command: sync GOAT colorway and per-size pricing data into the DB.

Typical workflow:
    # 1. Dry run — preview and save results to a file
    python manage.py seed_kicks --dry-run --output dry_run.json

    # 2. Review dry_run.json, then populate the DB from the file (no API calls)
    python manage.py seed_kicks --from-file dry_run.json

    # Or do a live sync directly (uses API):
    python manage.py seed_kicks

For every Shoe that has at least one insole-measured ShoeSize:
  1. Search GOAT once per measured size ("{brand} {model}" + size=X) so the
     result set is pre-filtered to colorways the API reports available in that
     size. Colorways with no inventory in any of our measured sizes never appear
     and never receive a detail fetch.
  2. Dedup colorways by goat_id across the per-size searches.
  3. Skip detail fetches for goat_ids already synced within RESYNC_DAYS, but
     touch last_synced_at so the stale-marking step does not clear their sizes.
  4. Fetch product detail to get per-size variants with price + availability.
     Only variants whose us_size is in the shoe's measured-size set are kept;
     any colorway with zero available variants in those sizes is dropped entirely.
  5. Upsert ShoeColorway (on goat_id) and ShoeColorwaySize (on colorway + us_size).
     Measured sizes absent from the GOAT response are written as is_available=False.
  6. Mark stale sizes unavailable: any ShoeColorwaySize whose colorway was not
     touched (last_synced_at < run_started) is flipped to is_available=False.
  7. Set Shoe.is_active based on whether any colorway was upserted this run.
"""

import json
import os
import time

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from backend.models import Shoe, ShoeColorway, ShoeColorwaySize

KICKS_API_BASE = "https://api.kicks.dev/v3"
MAX_PAGES = 3        # absolute ceiling — rarely reached with early-stop logic
PAGE_LIMIT = 100     # GOAT API max per page
SLEEP_BETWEEN = 0.1  # seconds between requests
RESYNC_DAYS = 6      # skip detail fetch for colorways synced this recently


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
        parser.add_argument(
            "--output",
            metavar="FILE",
            help="Save dry-run results to a JSON file (use with --dry-run).",
        )
        parser.add_argument(
            "--from-file",
            metavar="FILE",
            help="Populate the DB from a previously saved dry-run JSON file. No API calls made.",
        )

    def handle(self, *args, **options):
        from_file = options.get("from_file")
        output_file = options.get("output")
        dry_run = options["dry_run"]

        if from_file:
            self._populate_from_file(from_file)
            return

        # Live or dry-run mode — needs API key
        api_key = os.environ.get("KICKS_API_KEY")
        if not api_key:
            raise CommandError("KICKS_API_KEY is not set. Add it to your .env file.")

        auth = _auth_header(api_key)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no database writes.\n"))

        run_started = timezone.now()
        resync_cutoff = run_started - timezone.timedelta(days=RESYNC_DAYS)

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
        all_results = []  # collected for --output

        for shoe in shoes:
            insole_sizes = set(
                float(s.us_size)
                for s in shoe.sizes.all()
                if s.insole_length_in is not None
            )

            result = self._sync_shoe(shoe, insole_sizes, auth, dry_run, run_started, resync_cutoff)
            if result is None:
                skipped += 1
                if output_file:
                    all_results.append({
                        "shoe_id": shoe.pk,
                        "brand": shoe.brand,
                        "model": shoe.model,
                        "insole_sizes": sorted(insole_sizes),
                        "colorways": [],
                        "no_match": True,
                    })
            else:
                c, s, shoe_data = result
                total_colorways += c
                total_sizes += s
                if output_file:
                    all_results.append(shoe_data)

            time.sleep(SLEEP_BETWEEN)

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Colorways: {total_colorways}  "
            f"Available sizes: {total_sizes}  "
            f"Shoes with no match: {skipped}"
            + (" (dry run)" if dry_run else "")
        ))

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(all_results, f, indent=2)
            self.stdout.write(self.style.SUCCESS(f"Results saved to {output_file}"))

    # ------------------------------------------------------------------
    # Live / dry-run sync (hits the API)
    # ------------------------------------------------------------------

    def _sync_shoe(self, shoe, insole_sizes, auth, dry_run, run_started, resync_cutoff):
        """
        Sync one shoe via the API.
        Returns (colorways_upserted, sizes_upserted, shoe_data_dict) or None on skip.
        shoe_data_dict is always populated even in dry-run mode (for --output).
        """
        query = f"{shoe.brand} {shoe.model}"
        self.stdout.write(f"  {shoe.brand} {shoe.model}...")

        # --- Step 1: Search once per measured size ---
        # Passing size=X to the GOAT search returns only colorways available in
        # that size, so we never waste a detail fetch on irrelevant inventory.
        # Results are deduped by goat_id across the per-size searches.
        search_results_map = {}  # goat_id -> product

        try:
            for size in sorted(insole_sizes):
                for page in range(1, MAX_PAGES + 1):
                    resp = requests.get(
                        f"{KICKS_API_BASE}/goat/products",
                        params={"query": query, "limit": PAGE_LIMIT, "page": page, "size": size},
                        headers={"Authorization": auth},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    body = resp.json()
                    data = body.get("data") or []
                    meta = body.get("meta") or {}

                    new_on_page = 0
                    for product in data:
                        api_brand = (product.get("brand") or "").lower()
                        if not (shoe.brand.lower() in api_brand or api_brand in shoe.brand.lower()):
                            continue
                        goat_id = str(product.get("id") or "")
                        if not goat_id or goat_id in search_results_map:
                            continue
                        search_results_map[goat_id] = product
                        new_on_page += 1

                    if new_on_page == 0:
                        break  # no new colorways — stop paginating this size

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

        search_results = list(search_results_map.values())

        if not search_results:
            self.stdout.write(self.style.WARNING(f"    No GOAT results for our sizes — marking inactive"))
            if not dry_run:
                Shoe.objects.filter(pk=shoe.pk).update(is_active=False, last_synced_at=timezone.now())
            return None

        # Pre-load recently-synced goat_ids to skip their detail fetches
        fresh_goat_ids = set(
            ShoeColorway.objects.filter(
                shoe=shoe,
                goat_id__in=[str(p.get("id") or "") for p in search_results],
                last_synced_at__gte=resync_cutoff,
            ).values_list("goat_id", flat=True)
        )
        if fresh_goat_ids:
            self.stdout.write(f"    {len(fresh_goat_ids)} colorway(s) already fresh — skipping detail fetch")

        # --- Step 2: Detail fetch ---
        colorways_upserted = 0
        sizes_upserted = 0
        shoe_data = {
            "shoe_id": shoe.pk,
            "brand": shoe.brand,
            "model": shoe.model,
            "insole_sizes": sorted(insole_sizes),
            "colorways": [],
        }

        for product in search_results:
            slug = product.get("slug")
            if not slug:
                continue

            goat_id_from_search = str(product.get("id") or "")

            if goat_id_from_search in fresh_goat_ids:
                # Touch last_synced_at so the stale-marking query
                # (colorway__last_synced_at__lt=run_started) doesn't zero out
                # this colorway's sizes even though we skipped the detail fetch.
                if not dry_run:
                    ShoeColorway.objects.filter(
                        shoe=shoe, goat_id=goat_id_from_search
                    ).update(last_synced_at=timezone.now())
                colorways_upserted += 1
                continue

            try:
                detail_resp = requests.get(
                    f"{KICKS_API_BASE}/goat/products/{slug}",
                    headers={"Authorization": auth},
                    timeout=30,
                )
                detail_resp.raise_for_status()
                raw = detail_resp.json()
                detail = raw.get("data") or raw  # detail endpoint wraps under "data"
                time.sleep(SLEEP_BETWEEN)
            except requests.RequestException as exc:
                self.stderr.write(self.style.ERROR(
                    f"    [DETAIL ERROR] slug={slug}: {exc} — skipping colorway"
                ))
                time.sleep(SLEEP_BETWEEN)
                continue

            goat_id = str(detail.get("id") or goat_id_from_search)
            if not goat_id:
                continue

            name = _colorway_name(detail)
            image_url = detail.get("image_url") or None
            product_url = detail.get("link") or None
            sku = detail.get("sku") or None

            # Collect per-size data for this colorway
            colorway_sizes = []
            for variant in (detail.get("variants") or []):
                if variant.get("market") != "US" or variant.get("currency") != "USD":
                    continue
                try:
                    us_size = float(variant["size"])
                except (KeyError, TypeError, ValueError):
                    continue
                if us_size not in insole_sizes:
                    continue
                lowest_ask = variant.get("lowest_ask")
                colorway_sizes.append({
                    "us_size": us_size,
                    "price_usd": lowest_ask if lowest_ask else None,
                    "is_available": bool(variant.get("available", False)),
                })

            available_count = sum(1 for s in colorway_sizes if s["is_available"])
            if available_count == 0:
                continue  # No available inventory in our size — skip entirely

            self.stdout.write(
                f"    {'[DRY] ' if dry_run else ''}colorway: {name} (goat_id={goat_id})"
                f" — {available_count} available in size"
            )

            shoe_data["colorways"].append({
                "goat_id": goat_id,
                "name": name,
                "sku": sku,
                "image_url": image_url,
                "product_url": product_url,
                "sizes": colorway_sizes,
            })

            colorways_upserted += 1
            sizes_upserted += available_count

            if not dry_run:
                self._write_colorway(shoe, goat_id, name, sku, image_url, product_url, colorway_sizes, insole_sizes)

        # --- Step 3: Mark stale / update is_active ---
        if not dry_run:
            stale_qs = ShoeColorwaySize.objects.filter(
                colorway__shoe=shoe,
                colorway__last_synced_at__lt=run_started,
            )
            stale_count = stale_qs.update(is_available=False)
            if stale_count:
                self.stdout.write(self.style.WARNING(f"    Marked {stale_count} stale sizes unavailable"))

            Shoe.objects.filter(pk=shoe.pk).update(
                is_active=(colorways_upserted > 0),
                last_synced_at=timezone.now(),
            )

        self.stdout.write(f"    {colorways_upserted} colorways, {sizes_upserted} available in our size")
        return colorways_upserted, sizes_upserted, shoe_data

    # ------------------------------------------------------------------
    # File-based population (no API calls)
    # ------------------------------------------------------------------

    def _populate_from_file(self, filepath):
        if not os.path.exists(filepath):
            raise CommandError(f"File not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            all_results = json.load(f)

        self.stdout.write(f"Populating DB from {filepath}...\n")

        run_started = timezone.now()
        total_colorways = 0
        total_sizes = 0
        skipped = 0

        for shoe_data in all_results:
            shoe_id = shoe_data["shoe_id"]
            colorways = shoe_data.get("colorways", [])

            try:
                shoe = Shoe.objects.get(pk=shoe_id)
            except Shoe.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"  Shoe pk={shoe_id} not found — skipping"))
                skipped += 1
                continue

            insole_sizes = set(shoe_data.get("insole_sizes", []))

            if shoe_data.get("no_match") or not colorways:
                self.stdout.write(self.style.WARNING(
                    f"  {shoe.brand} {shoe.model} — no colorways in file, marking inactive"
                ))
                Shoe.objects.filter(pk=shoe_id).update(is_active=False, last_synced_at=timezone.now())
                skipped += 1
                continue

            self.stdout.write(f"  {shoe.brand} {shoe.model} — {len(colorways)} colorways")

            colorways_written = 0
            sizes_written = 0

            for cw in colorways:
                goat_id = cw["goat_id"]
                sizes_written_cw = self._write_colorway(
                    shoe,
                    goat_id,
                    cw["name"],
                    cw.get("sku"),
                    cw.get("image_url"),
                    cw.get("product_url"),
                    cw.get("sizes", []),
                    insole_sizes,
                )
                colorways_written += 1
                sizes_written += sizes_written_cw

            # Mark stale sizes from colorways not in this file
            stale_qs = ShoeColorwaySize.objects.filter(
                colorway__shoe=shoe,
                colorway__last_synced_at__lt=run_started,
            )
            stale_count = stale_qs.update(is_available=False)
            if stale_count:
                self.stdout.write(self.style.WARNING(f"    Marked {stale_count} stale sizes unavailable"))

            Shoe.objects.filter(pk=shoe_id).update(
                is_active=(colorways_written > 0),
                last_synced_at=timezone.now(),
            )

            total_colorways += colorways_written
            total_sizes += sizes_written

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Colorways written: {total_colorways}  "
            f"Sizes written: {total_sizes}  "
            f"Skipped: {skipped}"
        ))

    # ------------------------------------------------------------------
    # Shared DB write helper
    # ------------------------------------------------------------------

    def _write_colorway(self, shoe, goat_id, name, sku, image_url, product_url, sizes, insole_sizes):
        """
        Upsert one ShoeColorway and its ShoeColorwaySize rows.
        Returns the count of size rows written.
        """
        sizes_written = 0
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

            variant_sizes_seen = set()
            for size_row in sizes:
                us_size = float(size_row["us_size"])
                ShoeColorwaySize.objects.update_or_create(
                    colorway=colorway,
                    us_size=us_size,
                    defaults={
                        "price_usd": size_row.get("price_usd"),
                        "is_available": bool(size_row.get("is_available", False)),
                    },
                )
                variant_sizes_seen.add(us_size)
                sizes_written += 1

            # Mark any measured sizes not returned by GOAT as unavailable
            for missing_size in (insole_sizes - variant_sizes_seen):
                ShoeColorwaySize.objects.update_or_create(
                    colorway=colorway,
                    us_size=missing_size,
                    defaults={"is_available": False, "price_usd": None},
                )

        return sizes_written

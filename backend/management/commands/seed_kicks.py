"""
Management command: refresh GOAT colorway data using the goat_id slug
stored on each ShoeColorway row — no search step.

Only processes ShoeColorway rows whose product_url starts with goat.com.
The goat_id for GOAT-sourced colorways is the product slug
(e.g. "samba-og-b75806"), which maps directly to the detail endpoint.

Per colorway: refreshes name, sku, image_url, product_url, and
per-size price_usd / is_available.

Per shoe (after all colorways): rolls up shoe_image_url, product_url,
and price_usd from the cheapest available GOAT colorway size.

Typical usage:
    python manage.py seed_kicks
    python manage.py seed_kicks --shoe-id 17          # one specific shoe
    python manage.py seed_kicks --dry-run             # preview without writing
    python manage.py seed_kicks --force               # skip the 6-day freshness check

    # Fetch from API once, save raw responses — no DB writes:
    python manage.py seed_kicks --save-to goat_snapshot.json

    # Dry-run from a saved snapshot — zero API calls:
    python manage.py seed_kicks --load-from goat_snapshot.json --dry-run

    # Apply a saved snapshot to the DB:
    python manage.py seed_kicks --load-from goat_snapshot.json
"""

import json
import os
import time
from pathlib import Path

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from backend.models import Shoe, ShoeColorway, ShoeColorwaySize

KICKS_API_BASE  = "https://api.kicks.dev/v3"
GOAT_URL_PREFIX = "https://www.goat.com/"
SLEEP_BETWEEN   = 0.1   # seconds between API calls
RESYNC_DAYS     = 6     # skip detail fetch for colorways synced this recently


def _auth_header(api_key):
    return api_key if api_key.startswith("Bearer ") else f"Bearer {api_key}"


def _colorway_name(product):
    return (
        product.get("nickname")
        or product.get("colorway")
        or product.get("name")
        or "Unknown"
    )


class Command(BaseCommand):
    help = "Refresh GOAT colorway data (images, links, prices, availability) using stored goat_id slugs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--shoe-id",
            type=int,
            metavar="ID",
            help="Only sync colorways for this specific shoe DB pk.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview what would happen without writing to the database.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help=f"Ignore the {RESYNC_DAYS}-day freshness check and re-fetch all colorways.",
        )
        parser.add_argument(
            "--save-to",
            metavar="FILE",
            help=(
                "Fetch fresh data from the kicks.dev API and save raw responses to "
                "a JSON file. No database writes. Use --load-from later to apply."
            ),
        )
        parser.add_argument(
            "--load-from",
            metavar="FILE",
            help=(
                "Read colorway data from a previously saved JSON snapshot instead of "
                "calling the API. Combine with --dry-run to preview, or run without "
                "it to apply to the DB."
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_from_api(self, goat_colorways, auth):
        """
        Hit the kicks.dev API for each colorway slug.
        Returns a dict: {str(cw.pk): {"goat_id": slug, "raw": <API response>}}
        Colorways that error are stored with raw=None.
        """
        snapshot = {}
        total = len(goat_colorways)
        for i, cw in enumerate(goat_colorways, 1):
            slug = cw.goat_id
            self.stdout.write(f"  [{i}/{total}] fetching {slug} ...", ending="")
            self.stdout.flush()
            try:
                resp = requests.get(
                    f"{KICKS_API_BASE}/goat/products/{slug}",
                    headers={"Authorization": auth},
                    timeout=30,
                )
                resp.raise_for_status()
                raw = resp.json()
                self.stdout.write(" OK")
            except requests.RequestException as exc:
                self.stderr.write(self.style.ERROR(f" ERROR: {exc}"))
                raw = None
            snapshot[str(cw.pk)] = {"goat_id": slug, "raw": raw}
            time.sleep(SLEEP_BETWEEN)
        return snapshot

    def _load_snapshot(self, path):
        p = Path(path)
        if not p.exists():
            raise CommandError(f"Snapshot file not found: {path}")
        with p.open(encoding="utf-8") as fh:
            return json.load(fh)

    def _save_snapshot(self, snapshot, path):
        p = Path(path)
        with p.open("w", encoding="utf-8") as fh:
            json.dump(snapshot, fh, indent=2)
        self.stdout.write(self.style.SUCCESS(f"\nSnapshot saved to {p.resolve()}"))

    def _process_colorway(self, cw, detail, insole_sizes, dry_run, run_started):
        """
        Given a colorway ORM object and its API detail dict, compute what
        should change and optionally write it to the DB.

        Returns a rollup dict for the parent shoe.
        """
        name            = _colorway_name(detail)
        new_image_url   = detail.get("image_url") or cw.image_url
        new_product_url = detail.get("link") or cw.product_url
        sku             = detail.get("sku") or cw.sku

        colorway_sizes = []
        for variant in (detail.get("variants") or []):
            if variant.get("market") != "US" or variant.get("currency") != "USD":
                continue
            try:
                us_size = float(variant["size"])
            except (KeyError, TypeError, ValueError):
                continue
            if insole_sizes and us_size not in insole_sizes:
                continue
            lowest_ask   = variant.get("lowest_ask")
            is_available = bool(variant.get("available", False))
            colorway_sizes.append({
                "us_size":      us_size,
                "price_usd":    lowest_ask if lowest_ask else None,
                "is_available": is_available,
            })

        available_sizes = [s for s in colorway_sizes if s["is_available"]]
        prices          = [s["price_usd"] for s in available_sizes if s["price_usd"] is not None]
        min_price       = min(prices) if prices else None
        has_available   = bool(available_sizes)

        # Human-readable summary
        if available_sizes:
            price_str = f"${min_price:.2f}" if min_price else "price unknown"
            avail_str = f"{len(available_sizes)} size(s) avail @ {price_str}"
        else:
            avail_str = "no available sizes for this insole size"

        img_tag = "updated" if new_image_url   != cw.image_url   else "unchanged"
        lnk_tag = "updated" if new_product_url != cw.product_url else "unchanged"
        self.stdout.write(
            f"    {'[DRY] ' if dry_run else ''}{name}: "
            f"img={img_tag}, link={lnk_tag}, {avail_str}"
        )

        if colorway_sizes:
            for sz in colorway_sizes:
                flag = "avail" if sz["is_available"] else "OOS"
                price = f"${sz['price_usd']:.2f}" if sz["price_usd"] else "no price"
                self.stdout.write(f"         US {sz['us_size']}: {price} [{flag}]")
        else:
            self.stdout.write(f"         (no matching size variants in API response)")

        if not dry_run:
            with transaction.atomic():
                ShoeColorway.objects.filter(pk=cw.pk).update(
                    name=name,
                    sku=sku,
                    image_url=new_image_url,
                    product_url=new_product_url,
                    last_synced_at=run_started,
                )

                seen_sizes = set()
                for size_row in colorway_sizes:
                    us_sz = float(size_row["us_size"])
                    ShoeColorwaySize.objects.update_or_create(
                        colorway=cw,
                        us_size=us_sz,
                        defaults={
                            "price_usd":    size_row["price_usd"],
                            "is_available": size_row["is_available"],
                        },
                    )
                    seen_sizes.add(us_sz)

                # Insole sizes absent from GOAT response → mark unavailable
                for missing in (insole_sizes - seen_sizes):
                    ShoeColorwaySize.objects.update_or_create(
                        colorway=cw,
                        us_size=missing,
                        defaults={"is_available": False, "price_usd": None},
                    )

        return {
            "image_url":     new_image_url,
            "product_url":   new_product_url,
            "min_price":     min_price,
            "has_available": has_available,
        }

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        save_to   = options.get("save_to")
        load_from = options.get("load_from")
        dry_run   = options["dry_run"]
        force     = options["force"]

        if save_to and load_from:
            raise CommandError("--save-to and --load-from are mutually exclusive.")

        # --save-to always implies no DB writes (acts like --dry-run for the DB)
        if save_to:
            dry_run = True

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no database writes.\n"))

        # ── Build the queryset of shoes to process ────────────────────
        goat_shoe_ids = (
            ShoeColorway.objects
            .filter(product_url__startswith=GOAT_URL_PREFIX)
            .values_list("shoe_id", flat=True)
            .distinct()
        )
        qs = (
            Shoe.objects
            .filter(pk__in=goat_shoe_ids)
            .prefetch_related("sizes", "colorways")
        )
        if options.get("shoe_id"):
            qs = qs.filter(pk=options["shoe_id"])

        shoes = list(qs)
        if not shoes:
            self.stdout.write("No shoes with GOAT colorways found.")
            return

        # ── Collect all GOAT colorways we need to handle ──────────────
        run_started   = timezone.now()
        resync_cutoff = run_started - timezone.timedelta(days=RESYNC_DAYS)

        all_goat_colorways = []   # ordered list for snapshot building
        for shoe in shoes:
            for cw in shoe.colorways.all():
                if (cw.product_url or "").startswith(GOAT_URL_PREFIX):
                    all_goat_colorways.append(cw)

        # ── Decide data source: API or snapshot file ───────────────────
        if load_from:
            self.stdout.write(f"Loading snapshot from {load_from} ...\n")
            snapshot = self._load_snapshot(load_from)
            fetched_at = snapshot.get("fetched_at", "(unknown)")
            self.stdout.write(f"Snapshot fetched at: {fetched_at}\n")
        else:
            # Determine which colorways are stale enough to fetch
            to_fetch = []
            for cw in all_goat_colorways:
                if force or not cw.last_synced_at or cw.last_synced_at < resync_cutoff:
                    to_fetch.append(cw)

            if save_to:
                self.stdout.write(
                    f"Fetching {len(to_fetch)} colorway(s) from kicks.dev API "
                    f"(saving to {save_to}) ...\n"
                )
            else:
                self.stdout.write(
                    f"Syncing {len(shoes)} shoe(s) — "
                    f"{len(to_fetch)} colorway(s) to fetch, "
                    f"{len(all_goat_colorways) - len(to_fetch)} fresh (skipped).\n"
                )

            api_key = os.environ.get("KICKS_API_KEY")
            if not api_key:
                raise CommandError("KICKS_API_KEY is not set. Add it to your .env file.")
            auth = _auth_header(api_key)

            raw_snapshot = self._fetch_from_api(to_fetch, auth)
            snapshot = {
                "fetched_at": run_started.isoformat(),
                "colorways":  raw_snapshot,
            }

            if save_to:
                self._save_snapshot(snapshot, save_to)
                # Show a preview of what we fetched, then stop — no DB work.
                self.stdout.write("\n--- PREVIEW (no DB writes) ---\n")
                self._preview_snapshot(snapshot, shoes)
                return

        # ── Process each shoe using the snapshot (or live fetch) ───────
        self.stdout.write(f"\nProcessing {len(shoes)} shoe(s)...\n")

        total_updated = 0
        total_skipped = 0
        total_errors  = 0

        colorways_data = snapshot.get("colorways", {})

        for shoe in shoes:
            insole_sizes = {
                float(s.us_size)
                for s in shoe.sizes.all()
                if s.insole_length_in is not None
            }

            goat_colorways = [
                cw for cw in shoe.colorways.all()
                if (cw.product_url or "").startswith(GOAT_URL_PREFIX)
            ]

            self.stdout.write(
                f"  {shoe.brand} {shoe.model} — {len(goat_colorways)} GOAT colorway(s)"
            )

            shoe_rollup = []

            for cw in goat_colorways:
                cw_key = str(cw.pk)

                # If loading from a file, only process colorways present in snapshot
                if load_from and cw_key not in colorways_data:
                    # Not in snapshot — fall through to freshness-based skip
                    pass

                entry = colorways_data.get(cw_key)

                if entry is not None:
                    # Data came from snapshot (or live fetch this run)
                    raw    = entry.get("raw")
                    detail = (raw.get("data") or raw) if raw else None

                    if detail is None:
                        self.stderr.write(
                            self.style.ERROR(f"    [ERROR] cw{cw.pk} {cw.goat_id}: API returned no data")
                        )
                        total_errors += 1
                        continue

                    rollup = self._process_colorway(cw, detail, insole_sizes, dry_run, run_started)
                    shoe_rollup.append(rollup)
                    total_updated += 1

                else:
                    # Not in snapshot and not loading from file → check freshness
                    if not force and cw.last_synced_at and cw.last_synced_at >= resync_cutoff:
                        self.stdout.write(f"    skip (fresh): {cw.name}")
                        total_skipped += 1
                        shoe_rollup.append({
                            "image_url":     cw.image_url,
                            "product_url":   cw.product_url,
                            "min_price":     None,
                            "has_available": ShoeColorwaySize.objects.filter(
                                colorway=cw, is_available=True
                            ).exists(),
                        })
                    else:
                        self.stderr.write(
                            self.style.WARNING(f"    [WARN] cw{cw.pk} {cw.goat_id}: not in snapshot, skipping")
                        )
                        total_skipped += 1

            # ── Shoe-level rollup ──────────────────────────────────────
            available_rollup = [r for r in shoe_rollup if r["has_available"]]
            any_available    = bool(available_rollup)

            priced = [r for r in available_rollup if r["min_price"] is not None]
            best   = (
                min(priced, key=lambda r: r["min_price"]) if priced
                else (available_rollup[0] if available_rollup else None)
            )

            new_shoe_image = best["image_url"]   if best else None
            new_shoe_url   = best["product_url"] if best else None
            new_shoe_price = best["min_price"]   if best else None

            price_display = f"${new_shoe_price:.2f}" if new_shoe_price else "n/a"
            self.stdout.write(
                f"    >> shoe rollup: active={any_available}, "
                f"price={price_display}, "
                f"image={'set' if new_shoe_image else 'none'}, "
                f"link={'set' if new_shoe_url else 'none'}"
            )

            if not dry_run:
                update_fields = {
                    "is_active":      any_available,
                    "last_synced_at": run_started,
                }
                if new_shoe_image is not None:
                    update_fields["shoe_image_url"] = new_shoe_image
                if new_shoe_url is not None:
                    update_fields["product_url"] = new_shoe_url
                if new_shoe_price is not None:
                    update_fields["price_usd"] = new_shoe_price
                Shoe.objects.filter(pk=shoe.pk).update(**update_fields)

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Updated: {total_updated}  "
            f"Skipped (fresh): {total_skipped}  "
            f"Errors: {total_errors}"
            + (" (dry run)" if dry_run else "")
        ))

    def _preview_snapshot(self, snapshot, shoes):
        """Print a human-readable summary of what's in the snapshot."""
        colorways_data = snapshot.get("colorways", {})

        # Build a cw_pk → shoe lookup
        cw_shoe_map = {}
        for shoe in shoes:
            for cw in shoe.colorways.all():
                cw_shoe_map[str(cw.pk)] = (shoe, cw)

        for cw_key, entry in colorways_data.items():
            pair = cw_shoe_map.get(cw_key)
            if not pair:
                continue
            shoe, cw = pair
            raw    = entry.get("raw")
            detail = (raw.get("data") or raw) if raw else None
            if not detail:
                self.stderr.write(self.style.ERROR(f"  cw{cw_key}: API error — no data"))
                continue

            name = _colorway_name(detail)
            insole_sizes = {
                float(s.us_size)
                for s in shoe.sizes.all()
                if s.insole_length_in is not None
            }

            relevant = []
            for v in (detail.get("variants") or []):
                if v.get("market") != "US" or v.get("currency") != "USD":
                    continue
                try:
                    sz = float(v["size"])
                except (KeyError, TypeError, ValueError):
                    continue
                if insole_sizes and sz not in insole_sizes:
                    continue
                relevant.append(v)

            self.stdout.write(
                f"  [{shoe.pk}] {shoe.brand} {shoe.model} / cw{cw.pk} {name}"
            )
            if relevant:
                for v in relevant:
                    flag  = "avail" if v.get("available") else "OOS"
                    price = f"${v['lowest_ask']:.2f}" if v.get("lowest_ask") else "no price"
                    self.stdout.write(f"       US {v['size']}: {price} [{flag}]")
            else:
                self.stdout.write(f"       (no variants for insole size(s) {insole_sizes})")

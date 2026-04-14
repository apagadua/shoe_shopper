"""
Management command: enrich existing shoes in the DB with live data from KicksDB.

Iterates every Shoe row already in the database, searches KicksDB for it
across StockX then GOAT, and updates price, image, product URL, colorway,
sizes, and kicks_id in place. Never creates new shoes.

Usage:
    python manage.py seed_kicks
    python manage.py seed_kicks --dry-run
"""

import os
import time

import requests
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from backend.models import Shoe, ShoeSize

KICKS_API_BASE = "https://api.kicks.dev/v3"

SOURCES = [
    {
        "name": "StockX",
        "endpoint": "/stockx/products",
        "image_field": "image",
        "name_field": "title",
        "price_fn": lambda p: p.get("min_price") or 0,
        "variant_price_field": None,  # price is at product level
    },
    {
        "name": "GOAT",
        "endpoint": "/goat/products",
        "image_field": "image_url",
        "name_field": "name",
        "price_fn": lambda p: _goat_min_price(p),
        "variant_price_field": "lowest_ask",
    },
]


def _goat_min_price(product):
    variants = product.get("variants") or []
    prices = [v["lowest_ask"] for v in variants if v.get("lowest_ask")]
    return min(prices) if prices else 0


class Command(BaseCommand):
    help = "Enrich existing shoes with live data from KicksDB (price, image, sizes, colorway)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview what would be updated without writing to the database.",
        )

    def handle(self, *args, **options):
        api_key = os.environ.get("KICKS_API_KEY")
        if not api_key:
            raise CommandError(
                "KICKS_API_KEY is not set. Add it to your .env file."
            )

        auth_value = api_key if api_key.startswith("Bearer ") else f"Bearer {api_key}"
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no database writes."))

        shoes = list(Shoe.objects.only(
            'id', 'brand', 'model', 'kicks_id',
            'shoe_image_url', 'product_url', 'colorway', 'sku', 'price_usd',
        ))
        if not shoes:
            self.stdout.write("No shoes in the database to enrich.")
            return

        self.stdout.write(f"Enriching {len(shoes)} shoes from KicksDB...\n")

        updated = 0
        skipped = 0

        for shoe in shoes:
            result, source = self._fetch_best_match(shoe, auth_value)
            if result is None:
                self.stdout.write(self.style.WARNING(
                    f"  [SKIP] {shoe.brand} {shoe.model} — no match on StockX or GOAT"
                ))
                skipped += 1
                time.sleep(0.1)
                continue

            self._log(shoe, result, source, dry_run)

            if not dry_run:
                self._apply(shoe, result, source)

            updated += 1
            time.sleep(0.1)

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Updated: {updated}  Skipped (no match): {skipped}"
            + (" (dry run)" if dry_run else "")
        ))

    def _fetch_best_match(self, shoe, auth_value):
        """
        Try each source in order. Return (product, source) for the first source
        that finds a brand-matching result with a real price. Fall back to a
        brand-matching result with no price if all sources return $0.
        """
        query = f"{shoe.brand} {shoe.model}"
        zero_price_fallback = None

        for source in SOURCES:
            try:
                response = requests.get(
                    f"{KICKS_API_BASE}{source['endpoint']}",
                    params={"query": query, "per_page": 5},
                    headers={"Authorization": auth_value},
                    timeout=30,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                self.stderr.write(self.style.ERROR(
                    f"  [{source['name']}] API error for '{query}': {exc}"
                ))
                continue

            body = response.json()
            products = body if isinstance(body, list) else (body.get("data") or [])

            if not products:
                continue

            best = products[0]
            api_brand = (best.get("brand") or "").lower()
            if shoe.brand.lower() not in api_brand and api_brand not in shoe.brand.lower():
                continue

            price = source["price_fn"](best)
            if price and price > 0:
                return best, source

            # Brand matched but price is 0 — keep as fallback, try next source
            if zero_price_fallback is None:
                zero_price_fallback = (best, source)

            time.sleep(0.1)

        return zero_price_fallback or (None, None)

    def _apply(self, shoe, product, source):
        """Write KicksDB data onto the existing shoe row and sync its sizes."""
        variants = product.get("variants") or []

        shoe.kicks_id = shoe.kicks_id or product.get("id")
        shoe.shoe_image_url = shoe.shoe_image_url or product.get(source["image_field"]) or None
        shoe.product_url = shoe.product_url or product.get("link") or None
        shoe.colorway = shoe.colorway or product.get(source["name_field"]) or None
        shoe.sku = shoe.sku or product.get("sku") or None
        price = source["price_fn"](product)
        if price and price > 0:
            shoe.price_usd = price
        shoe.last_synced_at = timezone.now()
        shoe.save()

        # Sync sizes
        price_field = source["variant_price_field"]
        seen_sizes = set()
        for variant in variants:
            size_str = variant.get("size")
            if size_str is None:
                continue
            try:
                us_size = float(size_str)
            except (TypeError, ValueError):
                continue
            if not (1.0 <= us_size <= 20.0):
                continue
            available = True
            if price_field:
                available = bool(variant.get(price_field))
            ShoeSize.objects.update_or_create(
                shoe=shoe,
                us_size=us_size,
                width="regular",
                defaults={"is_available": available},
            )
            seen_sizes.add(us_size)

        if seen_sizes:
            shoe.sizes.exclude(us_size__in=seen_sizes).update(is_available=False)

    def _log(self, shoe, product, source, dry_run):
        prefix = "[DRY] " if dry_run else ""
        price = source["price_fn"](product)
        image = product.get(source["image_field"])
        self.stdout.write(
            f"  {prefix}[{source['name']}] {shoe.brand} {shoe.model}"
            f" → sku={product.get('sku')}"
            f", price=${price if price else 0}"
            f", image={'yes' if image else 'no'}"
        )

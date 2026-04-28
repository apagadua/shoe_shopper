"""
Probe the kicks.dev GOAT search endpoint with one shoe/size to understand:
  1. Whether the `size=X` param actually filters results (vs. being ignored).
  2. Whether search results include per-variant availability + price fields,
     making detail fetches unnecessary.

Usage:
    python manage.py probe_kicks_api
    python manage.py probe_kicks_api --shoe-id 42
    python manage.py probe_kicks_api --shoe-id 42 --size 10.5
"""

import json
import os
import time

import requests
from django.core.management.base import BaseCommand, CommandError

from backend.models import Shoe

KICKS_API_BASE = "https://api.kicks.dev/v3"


def _auth_header(api_key):
    return api_key if api_key.startswith("Bearer ") else f"Bearer {api_key}"


def _pp(label, data):
    print(f"\n{'='*60}")
    print(label)
    print('='*60)
    print(json.dumps(data, indent=2, default=str))


class Command(BaseCommand):
    help = "Probe kicks.dev GOAT search response schema for one shoe/size."

    def add_arguments(self, parser):
        parser.add_argument(
            "--shoe-id",
            type=int,
            metavar="ID",
            help="DB pk of the Shoe to probe (default: first shoe with insole measurements).",
        )
        parser.add_argument(
            "--size",
            type=float,
            metavar="SIZE",
            help="US size to pass as the size= param (default: first measured size for that shoe).",
        )
        parser.add_argument(
            "--count-only",
            action="store_true",
            default=False,
            help="Page through all results and report total colorway count. No detail fetches.",
        )

    def handle(self, *args, **options):
        api_key = os.environ.get("KICKS_API_KEY")
        if not api_key:
            raise CommandError("KICKS_API_KEY is not set. Add it to your .env file.")
        auth = _auth_header(api_key)

        # --- Pick shoe ---
        qs = Shoe.objects.prefetch_related("sizes").filter(
            sizes__insole_length_in__isnull=False
        ).distinct()

        if options["shoe_id"]:
            try:
                shoe = qs.get(pk=options["shoe_id"])
            except Shoe.DoesNotExist:
                raise CommandError(f"No shoe with pk={options['shoe_id']} that has insole measurements.")
        else:
            shoe = qs.first()
            if not shoe:
                raise CommandError("No shoes with insole measurements found in the DB.")

        insole_sizes = sorted(
            float(s.us_size) for s in shoe.sizes.all() if s.insole_length_in is not None
        )
        probe_size = options["size"] if options["size"] else insole_sizes[0]
        query = f"{shoe.brand} {shoe.model}"

        self.stdout.write(f"\nProbing: {shoe.brand} {shoe.model}  (pk={shoe.pk})")
        self.stdout.write(f"Measured sizes in DB: {insole_sizes}")
        self.stdout.write(f"Probe size: {probe_size}")
        self.stdout.write(f"Query string: '{query}'\n")

        headers = {"Authorization": auth}

        if options["count_only"]:
            self._count_colorways(shoe, query, insole_sizes, headers)
            return

        # --- Search WITHOUT size param ---
        self.stdout.write("Fetching search WITHOUT size= param (limit=2)...")
        resp_no_size = requests.get(
            f"{KICKS_API_BASE}/goat/products",
            params={"query": query, "limit": 2},
            headers=headers,
            timeout=30,
        )
        resp_no_size.raise_for_status()
        body_no_size = resp_no_size.json()

        # --- Search WITH size param ---
        self.stdout.write(f"Fetching search WITH size={probe_size} (limit=2)...")
        resp_with_size = requests.get(
            f"{KICKS_API_BASE}/goat/products",
            params={"query": query, "limit": 2, "size": probe_size},
            headers=headers,
            timeout=30,
        )
        resp_with_size.raise_for_status()
        body_with_size = resp_with_size.json()

        # --- Compare result counts ---
        data_no_size = body_no_size.get("data") or []
        data_with_size = body_with_size.get("data") or []
        meta_no_size = body_no_size.get("meta") or {}
        meta_with_size = body_with_size.get("meta") or {}

        self.stdout.write("\n--- Result count comparison ---")
        self.stdout.write(f"  Without size=: {len(data_no_size)} results on page, total={meta_no_size.get('total', '?')}")
        self.stdout.write(f"  With size={probe_size}: {len(data_with_size)} results on page, total={meta_with_size.get('total', '?')}")

        ids_no_size = {str(p.get("id")) for p in data_no_size}
        ids_with_size = {str(p.get("id")) for p in data_with_size}
        overlap = ids_no_size & ids_with_size
        self.stdout.write(f"  ID overlap between both pages: {len(overlap)}/{max(len(ids_no_size), len(ids_with_size))}")
        if ids_no_size == ids_with_size:
            self.stdout.write(self.style.WARNING(
                "  *** Identical result sets — size= param appears to be IGNORED ***"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "  *** Different result sets — size= param appears to FILTER results ***"
            ))

        # --- Print full response for manual inspection ---
        _pp("FULL RESPONSE — without size= (first result only)", data_no_size[0] if data_no_size else {})
        _pp("FULL RESPONSE — with size= (first result only)", data_with_size[0] if data_with_size else {})

        # --- Summarise key fields found ---
        self.stdout.write("\n--- Field presence in search results (first result, no-size) ---")
        first = data_no_size[0] if data_no_size else {}
        for field in ("id", "slug", "name", "nickname", "colorway", "brand", "sku",
                      "image_url", "link", "variants", "lowest_ask", "available",
                      "market", "currency"):
            present = field in first
            self.stdout.write(f"  {'[x]' if present else '[ ]'} {field}")

        variants = first.get("variants") or []
        if variants:
            self.stdout.write(f"\n  variants[0] keys: {list(variants[0].keys())}")
            self.stdout.write(self.style.SUCCESS(
                "  *** Search returns variants — detail fetch may be unnecessary ***"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "  *** No variants in search response — detail fetch still needed ***"
            ))

        # --- Fetch detail for first slug to compare ---
        slug = first.get("slug") or first.get("id")
        if slug:
            self.stdout.write(f"\nFetching detail for slug='{slug}'...")
            detail_resp = requests.get(
                f"{KICKS_API_BASE}/goat/products/{slug}",
                headers=headers,
                timeout=30,
            )
            detail_resp.raise_for_status()
            raw = detail_resp.json()
            detail = raw.get("data") or raw
            _pp(f"FULL DETAIL RESPONSE — {slug}", detail)

            detail_variants = detail.get("variants") or []
            if detail_variants:
                self.stdout.write(f"\n  detail variants[0] keys: {list(detail_variants[0].keys())}")
                our_size_variants = [
                    v for v in detail_variants
                    if v.get("market") == "US"
                    and v.get("currency") == "USD"
                    and float(v.get("size", -1)) in insole_sizes
                ]
                self.stdout.write(f"  Detail variants matching our sizes ({insole_sizes}): {len(our_size_variants)}")
                if our_size_variants:
                    _pp("Sample matching variant", our_size_variants[0])

    def _count_colorways(self, shoe, query, insole_sizes, headers):
        self.stdout.write(f"\nPaging through all results for '{query}'...\n")

        seen = {}  # goat_id -> name
        page = 1
        while True:
            resp = requests.get(
                f"{KICKS_API_BASE}/goat/products",
                params={"query": query, "limit": 100, "page": page},
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            body = resp.json()
            data = body.get("data") or []
            meta = body.get("meta") or {}

            new_this_page = 0
            brand_filtered = 0
            model_filtered = 0
            for product in data:
                api_brand = (product.get("brand") or "").lower()
                if not (shoe.brand.lower() in api_brand or api_brand in shoe.brand.lower()):
                    brand_filtered += 1
                    continue
                api_model = (product.get("model") or "").lower()
                if shoe.model.lower() not in api_model and api_model not in shoe.model.lower():
                    model_filtered += 1
                    continue
                goat_id = str(product.get("id") or "")
                if goat_id and goat_id not in seen:
                    seen[goat_id] = product.get("nickname") or product.get("colorway") or product.get("name") or "?"
                    new_this_page += 1

            total = meta.get("total", "?")
            self.stdout.write(
                f"  page {page}: {len(data)} results, {new_this_page} new colorways "
                f"({brand_filtered} brand-filtered, {model_filtered} model-filtered)"
                f" — running total: {len(seen)}  [API total={total}]"
            )

            if new_this_page == 0:
                self.stdout.write("  Early stop: no new colorways on this page.")
                break
            if meta.get("current_page", page) * 100 >= (total if isinstance(total, int) else 0):
                break
            if page >= 10:
                self.stdout.write("  Stopped at page 10 ceiling.")
                break

            page += 1
            time.sleep(0.1)

        self.stdout.write(self.style.SUCCESS(f"\nTotal unique colorways (brand-matched): {len(seen)}"))
        self.stdout.write(f"Detail fetches required per full sync: {len(seen)}")
        for goat_id, name in list(seen.items())[:20]:
            self.stdout.write(f"  {goat_id}: {name}")
        if len(seen) > 20:
            self.stdout.write(f"  ... and {len(seen) - 20} more")

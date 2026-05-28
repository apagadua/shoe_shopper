"""
Management command: show current sync status of all shoes in Supabase.

Prints a human-readable summary of every shoe — GOAT and non-GOAT — with
their current price, active status, last sync date, product URLs, and colorway
count. Run this before a sync to confirm what needs updating.

Usage:
    python manage.py show_sync_status
    python manage.py show_sync_status --stale-only   # only show shoes overdue for sync
    python manage.py show_sync_status --json          # machine-readable output
"""

import json
import re
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from backend.models import Shoe, ShoeColorway, ShoeColorwaySize


STALE_DAYS = 6  # matches seed_kicks RESYNC_DAYS and export freshness cutoff
GOAT_SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]*$')


def _is_goat(shoe, colorways):
    if shoe.kicks_id:
        return True
    if not colorways:
        return False
    return all(cw.goat_id and GOAT_SLUG_RE.match(cw.goat_id) for cw in colorways)


def _staleness(last_synced_at):
    if not last_synced_at:
        return "NEVER SYNCED"
    age = timezone.now() - last_synced_at
    days = age.days
    if days == 0:
        hours = age.seconds // 3600
        return f"{hours}h ago"
    return f"{days}d ago"


def _is_stale(last_synced_at):
    if not last_synced_at:
        return True
    return (timezone.now() - last_synced_at).days >= STALE_DAYS


class Command(BaseCommand):
    help = "Show current sync status of all shoes in Supabase."

    def add_arguments(self, parser):
        parser.add_argument(
            "--stale-only",
            action="store_true",
            default=False,
            help=f"Only show shoes not synced within the last {STALE_DAYS} days.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Output as JSON instead of human-readable table.",
        )

    def handle(self, *args, **options):
        shoes = list(
            Shoe.objects
            .prefetch_related("colorways__sizes", "sizes")
            .order_by("brand", "model")
        )

        now = timezone.now()
        rows = []

        for shoe in shoes:
            colorways = list(shoe.colorways.all())
            goat = _is_goat(shoe, colorways)
            stale = _is_stale(shoe.last_synced_at)

            if options["stale_only"] and not stale:
                continue

            # Colorway-level size availability summary
            available_sizes = set()
            colorway_rows = []
            for cw in colorways:
                sizes = list(cw.sizes.all())
                cw_available = [s for s in sizes if s.is_available]
                available_sizes.update(float(s.us_size) for s in cw_available)
                colorway_rows.append({
                    "id": cw.pk,
                    "goat_id": cw.goat_id,
                    "name": cw.name,
                    "product_url": cw.product_url,
                    "image_url": cw.image_url,
                    "last_synced_at": cw.last_synced_at.isoformat() if cw.last_synced_at else None,
                    "sizes": [
                        {
                            "us_size": float(s.us_size),
                            "price_usd": float(s.price_usd) if s.price_usd else None,
                            "is_available": s.is_available,
                        }
                        for s in sizes
                    ],
                })

            # Measured sizes from ShoeSize insole records
            measured_sizes = sorted(
                float(s.us_size) for s in shoe.sizes.all()
                if s.insole_length_in is not None
            )

            rows.append({
                "shoe_id": shoe.pk,
                "brand": shoe.brand,
                "model": shoe.model,
                "gender": shoe.gender,
                "source": "GOAT" if goat else "non-GOAT",
                "is_active": shoe.is_active,
                "price_usd": float(shoe.price_usd) if shoe.price_usd else None,
                "measured_sizes": measured_sizes,
                "product_url": shoe.product_url,
                "shoe_image_url": shoe.shoe_image_url,
                "last_synced_at": shoe.last_synced_at.isoformat() if shoe.last_synced_at else None,
                "staleness": _staleness(shoe.last_synced_at),
                "stale": stale,
                "colorway_count": len(colorways),
                "colorways": colorway_rows,
            })

        if options["json"]:
            self.stdout.write(json.dumps(rows, indent=2))
            return

        # ── Human-readable output ──────────────────────────────────────────

        goat_rows = [r for r in rows if r["source"] == "GOAT"]
        non_goat_rows = [r for r in rows if r["source"] == "non-GOAT"]
        stale_count = sum(1 for r in rows if r["stale"])

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"=== Shoe Sync Status --- {now.strftime('%Y-%m-%d %H:%M UTC')} ==="
        ))
        self.stdout.write(
            f"  {len(rows)} total shoes  |  "
            f"{sum(1 for r in rows if r['is_active'])} active  |  "
            f"{stale_count} stale (>{STALE_DAYS}d)  |  "
            f"{len(goat_rows)} GOAT  |  {len(non_goat_rows)} non-GOAT"
        )
        self.stdout.write("")

        # GOAT section
        self.stdout.write(self.style.WARNING(f"-- GOAT shoes ({len(goat_rows)}) -- managed by seed_kicks --"))
        for r in goat_rows:
            stale_flag = " !! STALE" if r["stale"] else ""
            active_flag = "+" if r["is_active"] else "-"
            price_str = f"${r['price_usd']:.2f}" if r["price_usd"] else "no price"
            self.stdout.write(
                f"  [{active_flag}] pk={r['shoe_id']:3d}  {r['brand']} {r['model']} ({r['gender']})  "
                f"{price_str}  {r['colorway_count']} colorways  "
                f"synced: {r['staleness']}{stale_flag}"
            )
            for cw in r["colorways"]:
                avail_sizes = [s for s in cw["sizes"] if s["is_available"]]
                prices = [f"${s['price_usd']:.2f}" for s in avail_sizes if s["price_usd"]]
                cw_last = cw["last_synced_at"][:10] if cw["last_synced_at"] else "never"
                self.stdout.write(
                    f"       cw={cw['id']:3d}  {(cw['name'] or '')[:40]:40s}  "
                    f"{len(avail_sizes)} avail sizes  "
                    f"{'  '.join(prices[:3])}{'...' if len(prices) > 3 else ''}  "
                    f"synced: {cw_last}"
                )
                if cw["product_url"]:
                    self.stdout.write(f"              url: {cw['product_url']}")

        self.stdout.write("")

        # Non-GOAT section
        self.stdout.write(self.style.WARNING(f"-- Non-GOAT shoes ({len(non_goat_rows)}) -- managed by pullmd/Chrome --"))
        for r in non_goat_rows:
            stale_flag = " !! STALE" if r["stale"] else ""
            active_flag = "+" if r["is_active"] else "-"
            price_str = f"${r['price_usd']:.2f}" if r["price_usd"] else "no price"
            sizes_str = ", ".join(str(s) for s in r["measured_sizes"])
            self.stdout.write(
                f"  [{active_flag}] pk={r['shoe_id']:3d}  {r['brand']} {r['model']} ({r['gender']})  "
                f"{price_str}  sizes: [{sizes_str}]  "
                f"synced: {r['staleness']}{stale_flag}"
            )
            if r["product_url"]:
                self.stdout.write(f"         url: {r['product_url']}")
            for cw in r["colorways"]:
                avail_sizes = [s for s in cw["sizes"] if s["is_available"]]
                prices = [f"${s['price_usd']:.2f}" for s in avail_sizes if s["price_usd"]]
                self.stdout.write(
                    f"         cw={cw['id']:3d}  {(cw['name'] or '')[:40]:40s}  "
                    f"{len(avail_sizes)} avail sizes  "
                    f"{'  '.join(prices[:3])}"
                )
                if cw["product_url"]:
                    self.stdout.write(f"              url: {cw['product_url']}")

        self.stdout.write("")

        # Stale summary
        stale_shoes = [r for r in rows if r["stale"]]
        if stale_shoes:
            self.stdout.write(self.style.WARNING(f"!!  {len(stale_shoes)} shoe(s) need syncing:"))
            for r in stale_shoes:
                self.stdout.write(
                    f"   pk={r['shoe_id']:3d}  {r['brand']} {r['model']}  "
                    f"source={r['source']}  last synced: {r['staleness']}"
                )
        else:
            self.stdout.write(self.style.SUCCESS("OK  All shoes are fresh -- no sync needed."))

        self.stdout.write("")

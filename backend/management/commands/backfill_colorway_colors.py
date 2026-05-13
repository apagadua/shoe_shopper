from django.core.management.base import BaseCommand
from django.utils import timezone

from backend.models import ShoeColorway
from backend.services.color_extraction import extract_color_palette_hex


class Command(BaseCommand):
    help = "Populate image-derived color palettes for stored shoe colorway image URLs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview eligible rows without writing to the database.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Recompute even when the stored source URL matches the image URL.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            metavar="N",
            help="Process at most N eligible colorways.",
        )
        parser.add_argument(
            "--shoe-id",
            type=int,
            metavar="ID",
            help="Only process colorways for this shoe DB primary key.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options.get("limit")

        qs = (
            ShoeColorway.objects
            .exclude(image_url__isnull=True)
            .exclude(image_url="")
            .select_related("shoe")
            .order_by("shoe_id", "id")
        )

        if options.get("shoe_id"):
            qs = qs.filter(shoe_id=options["shoe_id"])

        if limit is not None:
            if limit < 1:
                self.stderr.write(self.style.ERROR("--limit must be greater than zero."))
                return
            qs = qs[:limit]

        stats = {"total": 0, "ok": 0, "skipped": 0, "failed": 0}

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no database writes.\n"))

        for cw in qs:
            stats["total"] += 1
            label = self._label(cw)

            if not options["force"] and (
                cw.dominant_color_source_url == cw.image_url
                and cw.dominant_color_hex
                and cw.color_palette_hex
            ):
                stats["skipped"] += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"  DRY  {label} - would extract palette from {cw.image_url}"
                )
                stats["skipped"] += 1
                continue

            palette = extract_color_palette_hex(cw.image_url, max_colors=3)
            primary = palette[0] if palette else None

            if palette:
                ShoeColorway.objects.filter(pk=cw.pk).update(
                    dominant_color_hex=primary,
                    color_palette_hex=palette,
                    dominant_color_source_url=cw.image_url,
                    dominant_color_computed_at=timezone.now(),
                )
                hex_list = ", ".join(palette)
                self.stdout.write(f"  OK   {label} -> {hex_list}")
                stats["ok"] += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  FAIL {label} - extraction returned empty palette"
                    )
                )
                stats["failed"] += 1

        self.stdout.write("")
        self.stdout.write(f"Total eligible: {stats['total']}")
        self.stdout.write(f"  OK:      {stats['ok']}")
        self.stdout.write(f"  Failed:  {stats['failed']}")
        self.stdout.write(f"  Skipped: {stats['skipped']}")

    def _label(self, colorway):
        shoe = colorway.shoe
        shoe_label = f"{shoe.brand} {shoe.model}".strip()
        return f"[shoe={colorway.shoe_id} cw={colorway.pk}] {shoe_label} / {colorway.name}"

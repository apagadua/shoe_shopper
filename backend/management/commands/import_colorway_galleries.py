"""Import additional product-angle image URLs for shoe colorways."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from backend.models import ShoeColorway


class Command(BaseCommand):
    help = (
        "Import colorway galleries by goat_id. When an ID occurs in multiple "
        "source files, the last file processed wins."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--from",
            dest="sources",
            action="append",
            metavar="PATH",
            help=(
                "JSON source file (repeatable). Defaults to goat_galleries.json "
                "and scraped_galleries.json in the repository root."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report changes without writing to the database.",
        )

    def handle(self, *args, **options):
        source_paths = options["sources"] or [
            Path(settings.BASE_DIR) / "goat_galleries.json",
            Path(settings.BASE_DIR) / "scraped_galleries.json",
        ]

        galleries_by_goat_id = {}
        for source in source_paths:
            path = Path(source)
            try:
                with path.open(encoding="utf-8") as source_file:
                    records = json.load(source_file)
            except (OSError, json.JSONDecodeError) as exc:
                raise CommandError(f"Could not read {path}: {exc}") from exc

            if not isinstance(records, list):
                raise CommandError(f"Expected a JSON array in {path}")

            for record in records:
                if not isinstance(record, dict):
                    raise CommandError(f"Expected objects in {path}")
                goat_id = record.get("goat_id")
                gallery = record.get("gallery_image_urls")
                if not goat_id or not isinstance(gallery, list):
                    raise CommandError(
                        f"Each record in {path} must have a goat_id and a "
                        "gallery_image_urls list"
                    )
                galleries_by_goat_id[goat_id] = gallery

        colorways = {
            colorway.goat_id: colorway
            for colorway in ShoeColorway.objects.filter(
                goat_id__in=galleries_by_goat_id
            )
        }
        unmatched = [
            goat_id for goat_id in galleries_by_goat_id if goat_id not in colorways
        ]
        for goat_id in unmatched:
            self.stderr.write(
                self.style.WARNING(f"No colorway found for goat_id: {goat_id}")
            )

        updates = []
        empty_count = 0
        for goat_id, gallery in galleries_by_goat_id.items():
            colorway = colorways.get(goat_id)
            if colorway is None:
                continue
            colorway.gallery_image_urls = gallery
            updates.append(colorway)
            if not gallery:
                empty_count += 1

        if not options["dry_run"]:
            with transaction.atomic():
                ShoeColorway.objects.bulk_update(updates, ["gallery_image_urls"])

        suffix = " (dry run)" if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Rows updated: {len(updates)}; "
                f"rows with empty galleries: {empty_count}; "
                f"unmatched goat_ids: {len(unmatched)}{suffix}"
            )
        )

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from backend.management.commands.seed_kicks import Command as SeedKicksCommand
from backend.models import Shoe, ShoeColorway


pytestmark = pytest.mark.django_db


def make_colorway(goat_id):
    shoe = Shoe.objects.create(
        brand="Test Brand",
        model=f"Model {goat_id}",
        gender=Shoe.Gender.MEN,
    )
    return ShoeColorway.objects.create(
        shoe=shoe,
        goat_id=goat_id,
        name=f"Colorway {goat_id}",
    )


def write_source(path, records):
    path.write_text(json.dumps(records), encoding="utf-8")
    return str(path)


def test_importer_populates_galleries_and_last_source_wins(tmp_path):
    colorway = make_colorway("known")
    first = write_source(
        tmp_path / "first.json",
        [{"goat_id": "known", "gallery_image_urls": ["https://img/first.jpg"]}],
    )
    second = write_source(
        tmp_path / "second.json",
        [{"goat_id": "known", "gallery_image_urls": ["https://img/last.jpg"]}],
    )

    call_command("import_colorway_galleries", "--from", first, "--from", second)

    colorway.refresh_from_db()
    assert colorway.gallery_image_urls == ["https://img/last.jpg"]


def test_importer_writes_empty_gallery_and_warns_for_unmatched_id(tmp_path):
    colorway = make_colorway("empty")
    colorway.gallery_image_urls = ["https://img/old.jpg"]
    colorway.save(update_fields=["gallery_image_urls"])
    source = write_source(
        tmp_path / "galleries.json",
        [
            {"goat_id": "empty", "gallery_image_urls": []},
            {"goat_id": "missing", "gallery_image_urls": ["https://img/new.jpg"]},
        ],
    )
    stdout = StringIO()
    stderr = StringIO()

    call_command(
        "import_colorway_galleries", "--from", source, stdout=stdout, stderr=stderr
    )

    colorway.refresh_from_db()
    assert colorway.gallery_image_urls == []
    assert "rows with empty galleries: 1" in stdout.getvalue().lower()
    assert "missing" in stderr.getvalue()


def test_importer_dry_run_does_not_write(tmp_path):
    colorway = make_colorway("dry-run")
    source = write_source(
        tmp_path / "galleries.json",
        [{"goat_id": "dry-run", "gallery_image_urls": ["https://img/new.jpg"]}],
    )

    call_command("import_colorway_galleries", "--from", source, "--dry-run")

    colorway.refresh_from_db()
    assert colorway.gallery_image_urls == []


@pytest.mark.parametrize(
    ("detail_images", "expected"),
    [
        (
            ["https://img/side.jpg", "https://img/sole.jpg"],
            ["https://img/side.jpg", "https://img/sole.jpg"],
        ),
        # No images in the detail response clears the gallery so a colorway
        # that lost its gallery upstream gets cleared (spec tryon-01).
        (None, []),
    ],
)
def test_seed_kicks_maps_detail_images(detail_images, expected):
    colorway = make_colorway("seeded")
    colorway.gallery_image_urls = ["https://img/old.jpg"]
    colorway.save(update_fields=["gallery_image_urls"])
    detail = {"name": "Updated", "variants": []}
    if detail_images is not None:
        detail["images"] = detail_images

    SeedKicksCommand()._process_colorway(
        colorway,
        detail,
        insole_sizes=set(),
        dry_run=False,
        run_started=timezone.now(),
    )

    colorway.refresh_from_db()
    assert colorway.gallery_image_urls == expected

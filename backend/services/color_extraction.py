import io
import logging

import requests
from PIL import Image

logger = logging.getLogger(__name__)

FETCH_TIMEOUT = 12
MAX_CONTENT_LENGTH = 10 * 1024 * 1024
MAX_WORKING_DIMENSION = 160
MIN_ALPHA = 30
BACKGROUND_TOLERANCE = 30
MIN_COLOR_SHARE = 0.04


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Return an uppercase 7-character hex color for RGB channel values."""
    return f"#{r:02X}{g:02X}{b:02X}"


def _fetch_image(image_url: str) -> Image.Image | None:
    """Download image_url and return a loaded PIL Image, or None on failure."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ShoeShopper/1.0)",
    }
    if "converse.com" in image_url or "demandware.static" in image_url:
        headers["Referer"] = "https://www.converse.com"

    resp = None
    try:
        resp = requests.get(image_url, headers=headers, timeout=FETCH_TIMEOUT, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if content_type and "image" not in content_type.lower():
            logger.warning(
                "color_extraction: non-image content-type '%s' for %s",
                content_type,
                image_url,
            )
            return None

        data = resp.raw.read(MAX_CONTENT_LENGTH + 1)
        if len(data) > MAX_CONTENT_LENGTH:
            logger.warning("color_extraction: image too large for %s", image_url)
            return None

        img = Image.open(io.BytesIO(data))
        img.load()
        return img
    except Exception as exc:
        logger.warning("color_extraction: fetch failed for %s - %s", image_url, exc)
        return None
    finally:
        close = getattr(resp, "close", None)
        if callable(close):
            close()


def _border_rgb_pixels(img: Image.Image) -> list[tuple[int, int, int]]:
    width, height = img.size
    border_pixels = []
    for x in range(width):
        for y in (0, height - 1):
            r, g, b, a = img.getpixel((x, y))
            if a > MIN_ALPHA:
                border_pixels.append((r, g, b))
    for y in range(1, max(1, height - 1)):
        for x in (0, width - 1):
            r, g, b, a = img.getpixel((x, y))
            if a > MIN_ALPHA:
                border_pixels.append((r, g, b))
    return border_pixels


def _average_rgb(pixels: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    return (
        int(sum(p[0] for p in pixels) / len(pixels)),
        int(sum(p[1] for p in pixels) / len(pixels)),
        int(sum(p[2] for p in pixels) / len(pixels)),
    )


def _channel_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))


def _is_neutral_extreme(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    brightness = (r + g + b) / 3
    saturation = max(r, g, b) - min(r, g, b)
    return saturation < 20 and (brightness > 220 or brightness < 35)


def _rgb_distance_sq(
    a: tuple[int, int, int],
    b: tuple[int, int, int],
) -> int:
    """Squared Euclidean distance in RGB space."""
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def _merge_similar_palette_entries(
    entries: list[tuple[tuple[int, int, int], int]],
    min_distance: int = 40,
) -> list[tuple[tuple[int, int, int], int]]:
    """
    Merge entries whose colors are within `min_distance` Euclidean units.

    `entries` is a list of (rgb_tuple, count) sorted by count descending.
    Returns the merged list in count-descending order.
    """
    merged: list[tuple[tuple[int, int, int], int]] = []
    threshold_sq = min_distance ** 2
    for rgb, count in entries:
        placed = False
        for i, (existing_rgb, existing_count) in enumerate(merged):
            if _rgb_distance_sq(rgb, existing_rgb) < threshold_sq:
                merged[i] = (existing_rgb, existing_count + count)
                placed = True
                break
        if not placed:
            merged.append((rgb, count))
    merged.sort(key=lambda x: x[1], reverse=True)
    return merged


def color_palette_from_image(
    img: Image.Image,
    max_colors: int = 3,
) -> list[str]:
    """
    Return up to `max_colors` dominant visible colors as uppercase hex strings.

    Uses transparency filtering, cautious border background removal, neutral
    extreme filtering, and palette quantization. Returns [] if no visible
    pixels remain after filtering.
    """
    max_colors = max(1, max_colors)
    img = img.convert("RGBA")
    img.thumbnail((MAX_WORKING_DIMENSION, MAX_WORKING_DIMENSION), Image.LANCZOS)

    pixels = [p for p in img.getdata() if p[3] > MIN_ALPHA]
    if not pixels:
        return []

    original_pixels = pixels[:]
    border_pixels = _border_rgb_pixels(img)
    if border_pixels:
        bg_color = _average_rgb(border_pixels)
        filtered = [
            p
            for p in pixels
            if _channel_distance(p[:3], bg_color) > BACKGROUND_TOLERANCE
        ]
        min_remaining = max(20, int(len(original_pixels) * 0.05))
        if len(filtered) >= min_remaining:
            pixels = filtered
        else:
            pixels = original_pixels

    chromatic = [p for p in pixels if not _is_neutral_extreme(p[:3])]
    if len(chromatic) >= max(10, int(len(pixels) * 0.15)):
        pixels = chromatic

    if not pixels:
        return []

    n_clusters = max(8, max_colors * 4)
    sample_img = Image.new("RGB", (len(pixels), 1))
    sample_img.putdata([p[:3] for p in pixels])
    quantized = sample_img.quantize(colors=n_clusters, method=Image.Quantize.MEDIANCUT)

    raw_palette = quantized.getpalette()
    counts: dict[int, int] = {}
    for idx in quantized.getdata():
        counts[idx] = counts.get(idx, 0) + 1

    total = sum(counts.values())
    entries: list[tuple[tuple[int, int, int], int]] = sorted(
        (
            (
                (
                    raw_palette[idx * 3],
                    raw_palette[idx * 3 + 1],
                    raw_palette[idx * 3 + 2],
                ),
                cnt,
            )
            for idx, cnt in counts.items()
        ),
        key=lambda x: x[1],
        reverse=True,
    )

    merged = _merge_similar_palette_entries(entries, min_distance=40)

    result: list[str] = []
    for rgb, count in merged:
        if len(result) >= max_colors:
            break
        share = count / total if total else 0
        if share >= MIN_COLOR_SHARE or len(result) < 2:
            result.append(rgb_to_hex(*rgb))

    return result


def extract_color_palette_hex(
    image_url: str,
    max_colors: int = 3,
) -> list[str]:
    """
    Fetch image_url, extract a palette, and return uppercase #RRGGBB strings.

    Returns [] on any failure and never raises into callers.
    """
    if not image_url:
        return []

    img = _fetch_image(image_url)
    if img is None:
        return []

    try:
        return color_palette_from_image(img, max_colors=max_colors)
    except Exception as exc:
        logger.warning(
            "color_extraction: palette algorithm failed for %s - %s",
            image_url,
            exc,
        )
        return []


def dominant_color_from_image(img: Image.Image) -> str | None:
    """
    Return the dominant visible non-background color as uppercase hex.

    Delegates to color_palette_from_image; kept for backward compatibility.
    """
    palette = color_palette_from_image(img, max_colors=3)
    return palette[0] if palette else None


def extract_dominant_color_hex(image_url: str) -> str | None:
    """
    Fetch image_url, extract its dominant visible color, and return #RRGGBB.

    Returns None on any failure and never raises into callers.
    """
    palette = extract_color_palette_hex(image_url, max_colors=3)
    return palette[0] if palette else None

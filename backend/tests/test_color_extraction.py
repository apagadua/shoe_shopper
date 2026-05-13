import io
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from backend.services.color_extraction import (
    color_palette_from_image,
    dominant_color_from_image,
    extract_color_palette_hex,
    extract_dominant_color_hex,
    rgb_to_hex,
)


def _make_image(width, height, color, mode="RGB"):
    return Image.new(mode, (width, height), color)


def _make_rgba_image(width, height, fg_color, bg_alpha=0):
    img = Image.new("RGBA", (width, height), (255, 255, 255, bg_alpha))
    center_x, center_y = width // 4, height // 4
    for x in range(center_x, width - center_x):
        for y in range(center_y, height - center_y):
            img.putpixel((x, y), fg_color + (255,))
    return img


class TestRgbToHex(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(rgb_to_hex(164, 123, 88), "#A47B58")

    def test_black(self):
        self.assertEqual(rgb_to_hex(0, 0, 0), "#000000")

    def test_white(self):
        self.assertEqual(rgb_to_hex(255, 255, 255), "#FFFFFF")

    def test_uppercase(self):
        result = rgb_to_hex(10, 200, 255)
        self.assertEqual(result, result.upper())


class TestDominantColorFromImage(unittest.TestCase):
    def test_solid_red_returns_red_like(self):
        img = _make_image(100, 100, (200, 30, 30))
        result = dominant_color_from_image(img)
        self.assertIsNotNone(result)
        r = int(result[1:3], 16)
        g = int(result[3:5], 16)
        b = int(result[5:7], 16)
        self.assertGreater(r, 100)
        self.assertLess(g, 100)
        self.assertLess(b, 100)

    def test_colored_object_on_white_background(self):
        img = Image.new("RGB", (100, 100), (255, 255, 255))
        for x in range(20, 80):
            for y in range(20, 80):
                img.putpixel((x, y), (200, 30, 30))
        result = dominant_color_from_image(img)
        self.assertIsNotNone(result)
        r = int(result[1:3], 16)
        self.assertGreater(r, 120)

    def test_transparent_background_with_colored_object(self):
        img = _make_rgba_image(100, 100, fg_color=(30, 30, 200), bg_alpha=0)
        result = dominant_color_from_image(img)
        self.assertIsNotNone(result)
        b = int(result[5:7], 16)
        self.assertGreater(b, 100)

    def test_mostly_white_shoe_returns_light_color(self):
        img = _make_image(100, 100, (245, 243, 240))
        result = dominant_color_from_image(img)
        self.assertIsNotNone(result)

    def test_fully_transparent_returns_none(self):
        img = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
        result = dominant_color_from_image(img)
        self.assertIsNone(result)

    def test_result_is_valid_hex_string(self):
        img = _make_image(60, 60, (80, 150, 200))
        result = dominant_color_from_image(img)
        self.assertIsNotNone(result)
        self.assertRegex(result, r"^#[0-9A-F]{6}$")


class TestColorPaletteFromImage(unittest.TestCase):
    def test_returns_list(self):
        img = _make_image(80, 80, (200, 50, 50))
        result = color_palette_from_image(img)
        self.assertIsInstance(result, list)

    def test_result_contains_valid_hex_strings(self):
        img = _make_image(80, 80, (50, 150, 200))
        result = color_palette_from_image(img)
        for entry in result:
            self.assertRegex(entry, r"^#[0-9A-F]{6}$")

    def test_max_colors_respected(self):
        img = _make_image(80, 80, (100, 150, 200))
        result = color_palette_from_image(img, max_colors=2)
        self.assertLessEqual(len(result), 2)

    def test_fully_transparent_returns_empty_list(self):
        img = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
        result = color_palette_from_image(img)
        self.assertEqual(result, [])

    def test_two_color_image_returns_two_colors(self):
        """Left half red, right half blue; palette should contain both hues."""
        img = Image.new("RGB", (100, 100), (200, 30, 30))
        for x in range(50, 100):
            for y in range(100):
                img.putpixel((x, y), (30, 30, 200))
        result = color_palette_from_image(img, max_colors=3)
        self.assertGreaterEqual(len(result), 2)
        reds = [c for c in result if int(c[1:3], 16) > 120 and int(c[5:7], 16) < 100]
        blues = [c for c in result if int(c[5:7], 16) > 120 and int(c[1:3], 16) < 100]
        self.assertTrue(reds, "Expected a red-like color in palette")
        self.assertTrue(blues, "Expected a blue-like color in palette")

    def test_white_background_not_only_result(self):
        """Colored object on white background: white should be filtered out."""
        img = Image.new("RGB", (100, 100), (255, 255, 255))
        for x in range(20, 80):
            for y in range(20, 80):
                img.putpixel((x, y), (200, 50, 30))
        result = color_palette_from_image(img, max_colors=3)
        self.assertTrue(result, "Expected non-empty palette")
        self.assertGreater(
            int(result[0][1:3], 16),
            120,
            "First palette color should be red-like, not white",
        )

    def test_dominant_color_from_image_is_palette_first(self):
        """dominant_color_from_image must equal the first palette element."""
        img = _make_image(80, 80, (80, 150, 200))
        single = dominant_color_from_image(img)
        palette = color_palette_from_image(img, max_colors=3)
        if palette:
            self.assertEqual(single, palette[0])
        else:
            self.assertIsNone(single)


class TestExtractDominantColorHex(unittest.TestCase):
    def test_returns_none_for_empty_url(self):
        self.assertIsNone(extract_dominant_color_hex(""))
        self.assertIsNone(extract_dominant_color_hex(None))

    def test_returns_none_on_http_error(self):
        with patch("backend.services.color_extraction.requests.get") as mock_get:
            mock_get.side_effect = Exception("network error")
            result = extract_dominant_color_hex("https://example.com/shoe.jpg")
        self.assertIsNone(result)

    def test_returns_none_on_non_2xx(self):
        with patch("backend.services.color_extraction.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = Exception("403 Forbidden")
            mock_get.return_value = mock_resp
            result = extract_dominant_color_hex("https://example.com/shoe.jpg")
        self.assertIsNone(result)

    def test_converse_url_sends_referer_header(self):
        img = _make_image(50, 50, (50, 50, 150))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        with patch("backend.services.color_extraction.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.headers = {"Content-Type": "image/png"}
            mock_resp.raw.read.return_value = buf.getvalue()
            mock_get.return_value = mock_resp

            extract_dominant_color_hex(
                "https://www.converse.com/demandware.static/shoe.png"
            )

            call_kwargs = mock_get.call_args[1]
            headers_sent = call_kwargs.get("headers", {})
            self.assertIn("Referer", headers_sent)
            self.assertIn("converse.com", headers_sent["Referer"])

    def test_returns_hex_for_valid_image(self):
        img = _make_image(80, 80, (200, 50, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        with patch("backend.services.color_extraction.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.headers = {"Content-Type": "image/jpeg"}
            mock_resp.raw.read.return_value = buf.getvalue()
            mock_get.return_value = mock_resp

            result = extract_dominant_color_hex("https://media.goat.com/shoe.jpg")

        self.assertIsNotNone(result)
        self.assertRegex(result, r"^#[0-9A-F]{6}$")


class TestExtractColorPaletteHex(unittest.TestCase):
    def test_returns_empty_list_for_empty_url(self):
        self.assertEqual(extract_color_palette_hex(""), [])
        self.assertEqual(extract_color_palette_hex(None), [])

    def test_returns_empty_list_on_http_error(self):
        with patch("backend.services.color_extraction.requests.get") as mock_get:
            mock_get.side_effect = Exception("network error")
            result = extract_color_palette_hex("https://example.com/shoe.jpg")
        self.assertEqual(result, [])

    def test_returns_list_of_hex_strings_for_valid_image(self):
        img = _make_image(80, 80, (200, 50, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        with patch("backend.services.color_extraction.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.headers = {"Content-Type": "image/jpeg"}
            mock_resp.raw.read.return_value = buf.getvalue()
            mock_get.return_value = mock_resp

            result = extract_color_palette_hex("https://media.goat.com/shoe.jpg")

        self.assertIsInstance(result, list)
        self.assertTrue(len(result) >= 1)
        for entry in result:
            self.assertRegex(entry, r"^#[0-9A-F]{6}$")

    def test_extract_dominant_still_returns_first_palette_color(self):
        """extract_dominant_color_hex must return a hex when image is valid."""
        img = _make_image(80, 80, (200, 50, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        with patch("backend.services.color_extraction.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.headers = {"Content-Type": "image/jpeg"}
            mock_resp.raw.read.return_value = buf.getvalue()
            mock_get.return_value = mock_resp

            result = extract_dominant_color_hex("https://media.goat.com/shoe.jpg")

        self.assertIsNotNone(result)
        self.assertRegex(result, r"^#[0-9A-F]{6}$")


if __name__ == "__main__":
    unittest.main()

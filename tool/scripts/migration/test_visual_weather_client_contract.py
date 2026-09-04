#!/usr/bin/env python3
"""Static client resource contract for the visual-weather integration."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).parent))

from wzpy import WzCanvasProperty, WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
import add_visual_weather_client_items as generator  # noqa: E402

RESOURCES = (
    "Effect/WeatherAccum.img", "Effect/WeatherParticles.img",
    "Effect/WeatherPuddle.img", "Effect/WeatherSplash.img",
    "Map/Back/MapleMoonSky.img", "Map/Back/WeatherFog.img",
    "Map/Back/WeatherRainbow.img", "Map/Back/WeatherSnow.img",
    "Map/Obj/MapleMoonLamp.img", "Map/Obj/MapleMoonLamp2.img",
    "Sound/Weather.img",
)


class VisualWeatherClientContract(unittest.TestCase):
    def test_resources_parse_and_decode_every_canvas(self) -> None:
        canvas_count = 0
        for relative in RESOURCES:
            path = ROOT / "clien/Data" / relative
            self.assertTrue(path.is_file(), relative)
            image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
            image.parse()
            self.assertFalse(image.truncated, relative)
            self.assertEqual([], image.parse_warnings, relative)
            stack = list(image.root.children())
            while stack:
                node = stack.pop()
                stack.extend(node.children())
                if not isinstance(node, WzCanvasProperty):
                    continue
                pixels = decode_canvas(node, region="GMS").convert("RGBA")
                self.assertIsNotNone(pixels.getchannel("A").getbbox(),
                                     f"invisible canvas in {relative}: {node.name}")
                self.assertIn((node.format, node.format2), {(1, 0), (2, 0)})
                canvas_count += 1
        self.assertEqual(349, canvas_count)

    def test_cash_nodes_have_exact_contract(self) -> None:
        image = WzImage.from_bytes(generator.CLIENT_ITEM.read_bytes(),
                                   key=WzKey.for_region("GMS"), name="0512.img")
        image.parse()
        for name, (path, speed) in generator.ITEMS.items():
            node = image.root.child(name)
            self.assertIsNotNone(node, name)
            self.assertEqual(path, node.get("info/path").value)
            self.assertEqual(2, node.get("info/type").value)
            self.assertEqual(speed, node.get("info/speed").value)
            self.assertEqual(1, node.get("info/cash").value)

    def test_generator_is_idempotent(self) -> None:
        current = generator.CLIENT_ITEM.read_bytes()
        self.assertEqual(current, generator.patch(current))


if __name__ == "__main__":
    unittest.main()

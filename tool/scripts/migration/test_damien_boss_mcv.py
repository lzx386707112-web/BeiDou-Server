#!/usr/bin/env python3
"""Static contract for Damien scene/ground MCV field effects."""

from __future__ import annotations

import importlib.util
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/client-video"))

from export_soul_eclipse_mcv import FOURCC_XOR, HEIGHT, WIDTH  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzKey, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402

EXPORTER_PATH = ROOT / "tool/client-video/export_damien_boss_mcvs.py"
SPEC = importlib.util.spec_from_file_location("export_damien_boss_mcvs", EXPORTER_PATH)
assert SPEC and SPEC.loader
exporter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = exporter
SPEC.loader.exec_module(exporter)

DLL = ROOT / "tool/client-debug/karing-scene-compat/KaringSceneCompat.cpp"
EFFECT = ROOT / "clien/Data/Map/Effect.img"
JAVA = ROOT / "gms-server/src/main/java/org/gms/server/life/MobSkill.java"


def load_img(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    image.parse()
    assert not image.truncated
    assert image.parse_warnings == []
    return image


def mcv_contract(path: Path) -> dict[str, int]:
    data = path.read_bytes()
    assert len(data) >= 36
    (magic, version, header_size, encoded_fourcc, width, height,
     frame_count, flags, time_scale, reserved) = struct.unpack_from(
        "<4sHHIHHIB3xQI", data, 0
    )
    assert magic == b"MCV0"
    assert version == 0
    assert header_size == 36
    assert encoded_fourcc ^ FOURCC_XOR == int.from_bytes(b"VP90", "little")
    assert (width, height) == (WIDTH, HEIGHT)
    assert flags == 3
    assert time_scale == 1_000_000
    assert reserved == 0
    color_index = header_size
    alpha_index = color_index + frame_count * 8
    delay_index = alpha_index + frame_count * 8
    payload = delay_index + frame_count * 4
    assert payload <= len(data)
    colors = [struct.unpack_from("<II", data, color_index + index * 8) for index in range(frame_count)]
    alphas = [struct.unpack_from("<II", data, alpha_index + index * 8) for index in range(frame_count)]
    delays = [struct.unpack_from("<I", data, delay_index + index * 4)[0] for index in range(frame_count)]
    assert all(size > 0 for _, size in colors)
    assert all(size > 0 for _, size in alphas)
    assert all(delay > 0 for delay in delays)
    payload_size = len(data) - payload
    assert all(offset + size <= payload_size for offset, size in (*colors, *alphas))
    assert colors[0][0] == 0
    assert colors == sorted(colors)
    assert alphas == sorted(alphas)
    assert alphas[0][0] >= colors[-1][0] + colors[-1][1]
    return {"frames": frame_count, "duration": sum(delays)}


def main() -> int:
    errors: list[str] = []
    source = DLL.read_text(encoding="utf-8")
    if "damien-scene.mcv" not in source or "damien-ground.mcv" not in source:
        errors.append("KaringSceneCompat.cpp missing Damien MCV paths")
    if "kMarkerCodeCount = 40" not in source:
        errors.append("kMarkerCodeCount must include Damien codes 38-39")
    if "DetectDamienA4R4G4B4" not in source:
        errors.append("missing Damien marker decoder")

    java = JAVA.read_text(encoding="utf-8")
    if "customBossDemian/scene" not in java or "customBossDemian/groundBurst" not in java:
        errors.append("MobSkill.java must keep Damien effect paths")

    effect = load_img(EFFECT)
    parent = effect.root.child("customBossDemian")
    if not isinstance(parent, WzSubProperty):
        errors.append("missing customBossDemian")
    else:
        names = [child.name for child in effect.root.children()]
        if names.index("customBossDemian") > names.index("customBossSeren"):
            errors.append("customBossDemian sibling order")
        for spec in exporter.SCENES:
            child = parent.child(spec.marker_name)
            canvas = child.child("0") if isinstance(child, WzSubProperty) else None
            if not isinstance(canvas, WzCanvasProperty):
                errors.append(f"missing {spec.marker_name}/0")
                continue
            if (canvas.width, canvas.height, int(canvas.format), int(canvas.format2)) != (7, 5, 1, 0):
                errors.append(f"{spec.marker_name} is {canvas.width}x{canvas.height} fmt={canvas.format}")
                continue
            decoded = decode_canvas(canvas, region="GMS").convert("RGBA")
            pixels = list(decoded.getdata())[:5]
            decoded.close()
            if pixels != exporter.marker_pixels(spec.marker_code)[:5]:
                errors.append(f"{spec.marker_name} pixels {pixels}")
            path = ROOT / "clien/Data/Video" / spec.output_name
            if not path.is_file():
                errors.append(f"missing {spec.output_name}")
            else:
                try:
                    stats = mcv_contract(path)
                    expected = {
                        "damien-scene.mcv": (13, 1170),
                        "damien-ground.mcv": (36, 3240),
                    }[spec.output_name]
                    if (stats["frames"], stats["duration"]) != expected:
                        errors.append(
                            f"{spec.output_name} frames/duration="
                            f"{stats['frames']}/{stats['duration']} expected={expected}"
                        )
                except AssertionError as error:
                    errors.append(f"{spec.output_name} {error}")

    if errors:
        print("damien MCV contract failed:")
        for error in errors:
            print(f"  {error}")
        return 1
    print("damien MCV contract ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

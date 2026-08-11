#!/usr/bin/env python3
"""Static integration contract for the generated damage-skin feature."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzCanvasProperty, WzImage, WzKey, WzSubProperty, WzVectorProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


def require(path: str, text: str) -> None:
    content = (ROOT / path).read_text(encoding="utf-8")
    if text not in content:
        raise AssertionError(f"{path} is missing {text!r}")


def forbid(path: str, text: str) -> None:
    content = (ROOT / path).read_text(encoding="utf-8")
    if text in content:
        raise AssertionError(f"{path} still contains obsolete {text!r}")


def main() -> int:
    manifest = json.loads((ROOT / "docs/migrations/damage-skin-catalog.json").read_text(encoding="utf-8"))
    ids = [entry["id"] for entry in manifest["catalog"]]
    if len(ids) != 850 or ids != sorted(set(ids)) or ids[0] != 0:
        raise AssertionError("unexpected generated damage-skin catalog")
    if any(re.search(r"[#\r\n]", entry["name"]) for entry in manifest["catalog"]):
        raise AssertionError("damage-skin name contains NPC markup")

    require("gms-server/scripts-zh-CN/npc/9900009.js", "#fEffect/DamageSkin.img/preview/")
    require("gms-server/scripts-zh-CN/npc/9900009.js", "cm.setDamageSkin(skinId)")
    require("gms-server/src/main/java/org/gms/net/opcodes/SendOpcode.java", "DAMAGE_SKIN_UPDATE(0x17B)")
    require("tool/client-debug/set-item-compat/BeiDouSetItemCompat.cpp", "kDamageSkinUpdate = 0x017B")
    require("tool/client-debug/damage-skin-compat/BeiDouDamageSkinCompat.cpp", "kResourceManagerAddress = 0x00BF14E8")
    require("tool/client-debug/damage-skin-compat/BeiDouDamageSkinCompat.cpp", "kEffectHitAddress = 0x00437D0F")
    require("tool/client-debug/damage-skin-compat/BeiDouDamageSkinCompat.cpp", "0x986515D9")
    require("tool/client-debug/damage-skin-compat/BeiDouDamageSkinCompat.cpp", "QueryWzProperty")
    require("tool/client-debug/damage-skin-compat/BeiDouDamageSkinCompat.cpp", 'L"Effect/DamageSkin/%d.img"')
    require("tool/client-debug/damage-skin-compat/BeiDouDamageSkinCompat.cpp", "BDS_SetSkin")
    forbid("tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp", "BDS_TransformTexture")
    forbid("tool/client-debug/damage-skin-compat/BeiDouDamageSkinCompat.cpp", "DamageSkinTextureProbe.bin")
    forbid("tool/client-debug/damage-skin-compat/BeiDouDamageSkinCompat.cpp", "DamageSkin.dat")
    require("gms-server/src/main/java/org/gms/server/DamageSkinService.java", "damageSkinId")
    if (ROOT / "clien/DamageSkin.dat").exists():
        raise AssertionError("obsolete client-root DamageSkin.dat must be removed")

    image_path = ROOT / "clien/Data/Effect/DamageSkin.img"
    image = WzImage.from_bytes(image_path.read_bytes(), key=WzKey.for_region("GMS"), name=image_path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise AssertionError(f"unsafe DamageSkin.img parse: {image.parse_warnings}")
    if image.root.get("skin") is not None:
        raise AssertionError("preview DamageSkin.img must not contain runtime glyph trees")
    groups = ("NoRed0", "NoRed1", "NoCri0", "NoCri1")
    digits = tuple(str(value) for value in range(10))
    required_extras = {"NoRed0": ("Miss",), "NoCri1": ("effect",)}
    basic_path = ROOT / "clien/Data/Effect/BasicEff.img"
    basic = WzImage.from_bytes(basic_path.read_bytes(), key=WzKey.for_region("GMS"), name=basic_path.name)
    basic.parse()
    if basic.truncated or basic.parse_warnings:
        raise AssertionError(f"unsafe BasicEff.img parse: {basic.parse_warnings}")
    legacy_extra_pixels = {}
    for group, names in required_extras.items():
        for name in names:
            canvas = basic.root.get(f"{group}/{name}")
            if not isinstance(canvas, WzCanvasProperty):
                raise AssertionError(f"BasicEff.img is missing {group}/{name}")
            legacy_extra_pixels[(group, name)] = decode_canvas(canvas, region="GMS").convert("RGBA").tobytes()
    canvas_count = 0
    for skin_id in ids:
        if not isinstance(image.root.get(f"preview/{skin_id}"), WzCanvasProperty):
            raise AssertionError(f"missing damage-skin preview {skin_id}")
        skin_path = ROOT / f"clien/Data/Effect/DamageSkin/{skin_id}.img"
        skin = WzImage.from_bytes(skin_path.read_bytes(), key=WzKey.for_region("GMS"), name=skin_path.name)
        skin.parse()
        if skin.truncated or skin.parse_warnings:
            raise AssertionError(f"unsafe damage-skin IMG {skin_id}: {skin.parse_warnings}")
        for group in groups:
            group_node = skin.root.get(group)
            expected_names = digits + required_extras.get(group, ())
            if not isinstance(group_node, WzSubProperty) or tuple(
                child.name for child in group_node.children()
            ) != expected_names:
                raise AssertionError(f"legacy damage group layout mismatch {skin_id}/{group}")
            for digit in digits:
                if not isinstance(skin.root.get(f"{group}/{digit}"), WzCanvasProperty):
                    raise AssertionError(f"missing damage-skin glyph {skin_id}/{group}/{digit}")
                canvas_count += 1
            for name in required_extras.get(group, ()):
                canvas = skin.root.get(f"{group}/{name}")
                legacy = basic.root.get(f"{group}/{name}")
                if not isinstance(canvas, WzCanvasProperty) or not isinstance(legacy, WzCanvasProperty):
                    raise AssertionError(f"missing legacy damage node {skin_id}/{group}/{name}")
                origin = canvas.child("origin")
                legacy_origin = legacy.child("origin")
                if not isinstance(origin, WzVectorProperty) or not isinstance(legacy_origin, WzVectorProperty):
                    raise AssertionError(f"missing legacy damage node origin {skin_id}/{group}/{name}")
                if (
                    int(canvas.width),
                    int(canvas.height),
                    int(canvas.format),
                    int(canvas.format2),
                    int(origin.x),
                    int(origin.y),
                ) != (
                    int(legacy.width),
                    int(legacy.height),
                    int(legacy.format),
                    int(legacy.format2),
                    int(legacy_origin.x),
                    int(legacy_origin.y),
                ):
                    raise AssertionError(f"legacy damage node metadata mismatch {skin_id}/{group}/{name}")
                pixels = decode_canvas(canvas, region="GMS").convert("RGBA")
                if pixels.tobytes() != legacy_extra_pixels[(group, name)]:
                    raise AssertionError(f"legacy damage node pixels mismatch {skin_id}/{group}/{name}")
                canvas_count += 1
    if canvas_count != 35_700:
        raise AssertionError(f"unexpected WZ runtime Canvas count: {canvas_count}")
    print(
        f"damage-skin contract passed: {len(ids)} skins, "
        f"{canvas_count} WZ runtime Canvases, {manifest['skippedCount']} skipped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

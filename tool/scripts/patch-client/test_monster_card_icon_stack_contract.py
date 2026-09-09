#!/usr/bin/env python3
"""Contract: monster card inventory icons match drops and same cards stack."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT / "tool/wz-python"),
    str(ROOT / "tool/scripts/migration"),
    str(ROOT / "tool/scripts/patch-client"),
]

import migrate_arcane_river_expansion as arc  # noqa: E402
import unify_monster_card_drop_icon as patch  # noqa: E402
from wzpy import WzCanvasProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


def main() -> int:
    errors: list[str] = []
    image = patch.load_image(patch.CLIENT_ITEM)
    names = patch.card_ids(image)
    if len(names) != 343:
        errors.append(f"expected 343 monster cards, found {len(names)}")
    unique_icons = set()
    for name in names:
        card = image.root.get(name)
        icon = card.get("info/icon")
        raw = card.get("info/iconRaw")
        if not isinstance(icon, WzCanvasProperty) or not isinstance(raw, WzCanvasProperty):
            errors.append(f"{name} missing canvases")
            continue
        if (int(icon.format), int(icon.format2 or 0)) != (1, 0):
            errors.append(f"{name} icon is not format=1/0")
        if not patch.icon_matches_raw(icon, raw):
            errors.append(f"{name} inventory icon != drop icon")
        decoded = decode_canvas(icon, region="GMS").convert("RGBA")
        if decoded.getchannel("A").getbbox() is None:
            errors.append(f"{name} icon is fully transparent")
        unique_icons.add(decoded.tobytes())
        only = card.get("info/only")
        if only is None or int(only.value) != 0:
            errors.append(f"{name} only is not 0")
        if card.get("info/slotMax") is not None:
            errors.append(f"{name} unexpectedly gained slotMax in the client IMG")
    if len(unique_icons) != len(names):
        errors.append("inventory icons are not unique per monster card")

    xml = patch.SERVER_ITEM.read_text(encoding="utf-8")
    try:
        patch.verify_server_xml(xml, names)
    except RuntimeError as exc:
        errors.append(str(exc))

    if errors:
        print("monster card icon/stack contract failed:")
        for error in errors:
            print(f"  {error}")
        return 1
    print(f"monster card icon/stack contract passed for {len(names)} cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

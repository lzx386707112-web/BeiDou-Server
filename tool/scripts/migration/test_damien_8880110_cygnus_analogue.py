#!/usr/bin/env python3
"""8880110 uses Cygnus node/combat structure with Damien canvases."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
import rewrite_damien_8880110_as_cygnus as rewrite  # noqa: E402
from migrate_twilight_perion_monster_park import load_checked  # noqa: E402
from wzpy import WzUolProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    rewrite.verify_client()
    rewrite.verify_xml()
    if sha256(rewrite.client_cygnus()) == sha256(demian.client_mob_path(8880110)):
        raise SystemExit("8880110.img is still a Cygnus byte copy")
    image = load_checked(demian.client_mob_path(8880110), arc.GMS_KEY)
    cygnus = load_checked(rewrite.client_cygnus(), arc.GMS_KEY)
    if (int(image.root.get("stand/0").width), int(image.root.get("stand/0").height)) == (
        int(cygnus.root.get("stand/0").width),
        int(cygnus.root.get("stand/0").height),
    ):
        raise SystemExit("stand/0 still matches Cygnus art size")
    for path in ("stand/0", "attack1/0", "attack1/info/hit/0", "attack3/info/areaWarning/1", "move/0"):
        node = image.root.get(path)
        if node is None:
            raise SystemExit(f"missing {path}")
        if isinstance(node, WzUolProperty):
            raise SystemExit(f"{path} should be a canvas")
        decoded = decode_canvas(node, region="GMS").convert("RGBA")
        if decoded.getbbox() is None:
            raise SystemExit(f"{path} has no visible pixels")
        if (int(node.format), int(node.format2)) != (1, 0):
            raise SystemExit(f"{path} is not ARGB4444")
        decoded.close()
    java = (ROOT / "gms-server/src/main/java/org/gms/server/life/DamienBossCompat.java").read_text(
        encoding="utf-8"
    )
    if "onSkill2Cast" not in java or "planSkill2Orbs" not in java:
        raise SystemExit("DamienBossCompat missing skill2 orb routing")
    if "usesCustomCombat" in java or "STIGMA_CAP" in java:
        raise SystemExit("DamienBossCompat still has custom combat")
    event = (ROOT / "gms-server/scripts/event/DamienBattle.js").read_text(encoding="utf-8")
    if "startPhase(map, boss, 1)" in event:
        raise SystemExit("DamienBattle still starts a phase-one Encounter")
    print("8880110 cygnus structure + Damien art contract ok", sha256(demian.client_mob_path(8880110)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

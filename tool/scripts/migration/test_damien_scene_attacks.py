#!/usr/bin/env python3
"""Contract for Damien's complete TMS attack, skill, and field-effect projection."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(ROOT / "tool/scripts/migration")]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
import patch_damien_tms_boss_actions as patcher  # noqa: E402
from wzpy import WzCanvasProperty, WzSubProperty, WzUolProperty  # noqa: E402

EFFECT = ROOT / "clien/Data/Map/Effect.img"


def scalar(node, name):
    child = node.child(name)
    return None if child is None else int(child.value)


def canvas_signature(node):
    result = {}
    for child, path in arc.walk(node):
        if isinstance(child, WzCanvasProperty):
            origin = child.child("origin")
            result[path] = (
                "canvas",
                int(child.width),
                int(child.height),
                None if origin is None else (int(origin.x), int(origin.y)),
                scalar(child, "delay"),
            )
        elif isinstance(child, WzUolProperty):
            result[path] = ("uol", str(child.value))
    return result


def main() -> int:
    errors = []
    for mob_id in demian.BOSS_IDS:
        image = arc.load_image(demian.client_mob_path(mob_id), arc.GMS_KEY)
        expected_roots = demian.LEGACY_BOSS_TOP_LEVEL_BY_MOB[mob_id]
        roots = tuple(child.name for child in image.root.children())
        if roots != expected_roots:
            errors.append(f"{mob_id} root order {roots}")

        table = image.root.get("info/skill")
        actual_table = [
            {entry.name: int(entry.value) for entry in child.children()}
            for child in table.children()
        ]
        if actual_table != list(demian.SKILLS_BY_MOB[mob_id]):
            errors.append(f"{mob_id} skill table differs from TMS")

        projection = patcher.build_boss_projection(mob_id)
        for name in ("move", *patcher.ATTACKS_BY_MOB[mob_id], *patcher.SKILL_ACTIONS_BY_MOB[mob_id]):
            target = image.root.child(name)
            if name in demian.STUB_ACTIONS.get(mob_id, ()):
                canvases = [
                    child for child in target.children()
                    if isinstance(child, WzCanvasProperty) and child.name.isdigit()
                ]
                if len(canvases) != 1 or (canvases[0].width, canvases[0].height) != (1, 1):
                    errors.append(f"{mob_id}/{name} was not stubbed for Flash safety")
                continue
            expected = projection[name]
            if canvas_signature(target) != canvas_signature(expected):
                errors.append(f"{mob_id}/{name} dimensions, origins, delays, or UOLs differ from TMS")

    skills = arc.load_image(patcher.CLIENT_MOB_SKILL, arc.GMS_KEY)
    if not isinstance(skills.root.get("142/level/1"), WzSubProperty):
        errors.append("missing client MobSkill 142/1")
    for table in demian.SKILLS_BY_MOB.values():
        for entry in table:
            if entry["skill"] in {170, 174, 176, 186, 201, 214, 215} or (
                entry["skill"] == 142 and entry["level"] != 1
            ):
                errors.append(f"Damien still references unsafe MobSkill {entry['skill']}/{entry['level']}")
    for mob_id in patcher.DEPENDENCY_MOBS:
        if not demian.client_mob_path(mob_id).is_file():
            errors.append(f"missing client dependency mob {mob_id}")
        if not demian.server_mob_path("wz", mob_id).is_file():
            errors.append(f"missing server dependency mob {mob_id}")

    effect = arc.load_image(EFFECT, arc.GMS_KEY)
    marker_parent = effect.root.child("customBossDemian")
    for name in ("scene", "groundBurst"):
        marker = marker_parent.get(f"{name}/0") if marker_parent else None
        if not isinstance(marker, WzCanvasProperty) or (marker.width, marker.height) != (7, 5):
            errors.append(f"missing Damien MCV marker {name}")

    move_source = (ROOT / "gms-server/src/main/java/org/gms/net/server/channel/handlers/MoveLifeHandler.java").read_text()
    if "inRangeInclusive(rawActivity, 42, 61)" not in move_source:
        errors.append("MoveLifeHandler does not accept Damien action 10")
    compat = (ROOT / "gms-server/src/main/java/org/gms/server/life/DamienBossCompat.java").read_text()
    for token in ("customBossDemian/groundBurst", "customBossDemian/scene", "skillId == 142"):
        if token not in compat:
            errors.append(f"DamienBossCompat missing {token}")

    if errors:
        print("damien complete TMS contract failed:")
        for error in errors:
            print(f"  {error}")
        return 1
    print("damien complete TMS attacks/skills/effects contract ok: phase1=6+4 phase2=7+10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

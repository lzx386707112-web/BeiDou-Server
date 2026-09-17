#!/usr/bin/env python3
"""Damien no longer uses FIELD_EFFECT MCV; keep skill2 gold orbs and Java clean."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import patch_damien_skill2_gold_orbs as gold_orbs  # noqa: E402
from wzpy import WzCanvasProperty, WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402

DLL = ROOT / "tool/client-debug/karing-scene-compat/KaringSceneCompat.cpp"
JAVA = ROOT / "gms-server/src/main/java/org/gms/server/life/DamienBossCompat.java"
EXPORTER = ROOT / "tool/client-video/export_damien_boss_mcvs.py"


def load_img(path: Path) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    image.parse()
    assert not image.truncated
    assert image.parse_warnings == []
    return image


def main() -> int:
    errors: list[str] = []
    source = DLL.read_text(encoding="utf-8")
    for name in ("damien-scene.mcv", "damien-ground.mcv", "DetectDamienA4R4G4B4"):
        if name in source:
            errors.append(f"KaringSceneCompat.cpp still has Damien MCV logic: {name}")
    if EXPORTER.is_file():
        errors.append("export_damien_boss_mcvs.py should be deleted")
    java = JAVA.read_text(encoding="utf-8")
    if "onSkill2Cast" not in java:
        errors.append("DamienBossCompat missing skill2 orb routing")
    if "onAttackStart" in java or "STIGMA_CAP" in java:
        errors.append("DamienBossCompat must not restore stigma / onAttackStart MCV combat")
    if "damien-ground.mcv" in java or "damien-scene.mcv" in java:
        errors.append("DamienBossCompat must not play Damien MCV files")
    if "SKILL2_GROUND_EFFECT" not in java or "customBossDemian/groundBurst" not in java:
        errors.append("DamienBossCompat missing skill2 ground-burst FIELD_EFFECT")
    for name in ("damien-scene.mcv", "damien-ground.mcv"):
        if (ROOT / "clien/Data/Video" / name).is_file():
            errors.append(f"{name} should stay deleted")

    orb = ROOT / "clien/Data/Mob/8880112.img"
    if not orb.is_file():
        errors.append("missing client skill2 orb 8880112.img")
    else:
        image = load_img(orb)
        if image.root.get("fly/0/_outlink") is not None:
            errors.append("8880112 must not outlink to 8880169 butterflies")
        info = image.root.child("info")
        if info is None or int(getattr(info.child("firstAttack"), "value", 0) or 0) != 1:
            errors.append("8880112 must firstAttack=1")
        attack_info = image.root.get("attack1/info")
        canvases: list = []
        if attack_info is None:
            errors.append("8880112 missing attack1/info ball contract")
        else:
            ball_type = attack_info.child("type")
            if ball_type is None or int(ball_type.value) != 2:
                errors.append("8880112 attack1/info type must be 2")
            if attack_info.child("bulletSpeed") is None:
                errors.append("8880112 missing bulletSpeed")
            ball = attack_info.child("ball")
            canvases = [
                child for child in ball.children()
                if isinstance(child, WzCanvasProperty) and child.name.isdigit()
            ] if ball is not None else []
            if len(canvases) < 4 or canvases[0].width < 40 or canvases[0].width >= 160:
                errors.append("8880112 attack1/info/ball missing 8880101 sphere bullets")
            else:
                decoded = decode_canvas(canvases[0], region="GMS").convert("RGBA")
                if decoded.getbbox() is None:
                    errors.append("8880112 ball decoded empty")
                decoded.close()
            hit = attack_info.child("hit")
            attach = hit.child("attach") if hit is not None else None
            if attach is None or int(attach.value) != 1:
                errors.append("8880112 attack1/info/hit missing attach=1")
        sources = gold_orbs.ball_sources()
        if canvases and sources:
            expected = gold_orbs.scaled_size(int(sources[0].width), int(sources[0].height))
            if (int(canvases[0].width), int(canvases[0].height)) != expected:
                errors.append("8880112 ball size must match 8880101 attack3/info/ball")

    if errors:
        print("damien MCV removal contract failed:")
        for error in errors:
            print(f"  {error}")
        return 1
    print("damien MCV removal contract ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

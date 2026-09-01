#!/usr/bin/env python3
"""Static contract checks for the complete legacy Lucid controller."""

from __future__ import annotations

import importlib.util
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(ROOT / "tool/client-video"))

from wzpy import WzCanvasProperty, WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402


EXPORTER_PATH = ROOT / "tool/client-video/export_lucid_boss_mcvs.py"
SPEC = importlib.util.spec_from_file_location("export_lucid_boss_mcvs", EXPORTER_PATH)
assert SPEC and SPEC.loader
exporter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = exporter
SPEC.loader.exec_module(exporter)


def load_img(path: Path) -> WzImage:
    image = WzImage.from_bytes(
        path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
    )
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
    assert encoded_fourcc ^ exporter.FOURCC_XOR == int.from_bytes(b"VP90", "little")
    assert (width, height) == (1280, 720)
    assert flags == 3
    assert time_scale == 1_000_000
    assert reserved == 0
    color_index = header_size
    alpha_index = color_index + frame_count * 8
    delay_index = alpha_index + frame_count * 8
    payload = delay_index + frame_count * 4
    assert payload <= len(data)
    colors = [struct.unpack_from("<II", data, color_index + index * 8)
              for index in range(frame_count)]
    alphas = [struct.unpack_from("<II", data, alpha_index + index * 8)
              for index in range(frame_count)]
    delays = [struct.unpack_from("<I", data, delay_index + index * 4)[0]
              for index in range(frame_count)]
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


def test_lucid_mcvs_have_complete_timeline_contracts():
    for scene in exporter.SCENES:
        path = ROOT / "clien/Data/Video" / scene.output_name
        assert path.is_file()
        contract = mcv_contract(path)
        assert contract["frames"] == len(exporter.frame_delays(scene))
        assert contract["duration"] == scene.duration_ms


def test_every_tms_boss_lucid_root_is_explicitly_accounted_for():
    proxy, _ = exporter.load_images()
    roots = [child.name for child in proxy.root.children()]
    assert roots == [
        "Lucid", "Butterfly", "Dragon", "DragonShadow", "HurdleArea",
        "LaserRain", "Horn", "StainedGlass", "Shoot", "RushLucid",
        "WeatherMessage", "Fury", "BombObject",
    ]
    documentation = (
        ROOT / "docs/migrations/lucid-expedition.md"
    ).read_text(encoding="utf-8")
    for name in roots:
        assert name in documentation


def test_phantom_barrage_has_projectile_paths_and_timed_hit_effects():
    proxy, _ = exporter.load_images()
    scene = next(scene for scene in exporter.SCENES if scene.key == "phantom-barrage")
    layers = exporter.scene_layers(proxy, exporter.arc.CanvasMaterializer(), scene)
    impacts = [
        exporter.PHANTOM_PREPARE_MS + index * exporter.PHANTOM_HIT_INTERVAL_MS
        for index in range(exporter.PHANTOM_HIT_COUNT)
    ]
    projectiles = [layer for layer in layers if layer.motion is not None]
    assert len(projectiles) == exporter.PHANTOM_HIT_COUNT
    assert [layer.end_ms for layer in projectiles] == impacts
    assert all(
        layer.end_ms - layer.start_ms == exporter.PHANTOM_PROJECTILE_TRAVEL_MS
        for layer in projectiles
    )

    hit_duration = exporter.sequence_duration(exporter.load_sequence(
        proxy, exporter.arc.CanvasMaterializer(), "Shoot/hit", 60,
    ))
    hits = [
        layer for layer in layers
        if layer.motion is None
        and layer.start_ms in impacts
        and layer.end_ms - layer.start_ms == hit_duration
    ]
    assert len(hits) == exporter.PHANTOM_HIT_COUNT
    assert [layer.offsets[0] for layer in hits] == [
        layer.motion[-1] for layer in projectiles
    ]


def test_dragon_shadow_and_end_actions_are_in_both_dragon_timelines():
    proxy, _ = exporter.load_images()
    for key in ("dragon-p1", "dragon-p2"):
        phase = "phase1" if key == "dragon-p1" else "phase2"
        scene = next(scene for scene in exporter.SCENES if scene.key == key)
        layers = exporter.scene_layers(proxy, exporter.arc.CanvasMaterializer(), scene)
        assert any(
            layer.motion is not None
            and layer.frames[0][0].child("_outlink").value.startswith(
                "Etc/_Canvas/BossLucid.img/DragonShadow/"
            )
            for layer in layers
        )
        endings = [layer for layer in layers if layer.start_ms == 10050]
        assert len(endings) == 1
        assert endings[0].end_ms == 11850
        dragon_offset = (exporter.DRAGON_RIGHT_OFFSETS[phase],)
        assert [layers[index].offsets for index in (4, 6, 7, 8)] == [
            dragon_offset,
            dragon_offset,
            dragon_offset,
            dragon_offset,
        ]
        assert all(layers[index].offsets == ((0, 0),) for index in (1, 2, 3, 5))


def test_rush_uses_all_tms_path_points_instead_of_a_full_map_impact():
    proxy, _ = exporter.load_images()
    scene = next(scene for scene in exporter.SCENES if scene.key == "rush")
    layers = exporter.scene_layers(proxy, exporter.arc.CanvasMaterializer(), scene)
    path = exporter.rush_screen_path()
    assert len(path) == 15
    assert path[0][0] == 0
    assert path[-1][0] == exporter.RUSH_DURATION_MS
    assert all(layer.path == path for layer in layers)
    assert [point for point, _ in exporter.RUSH_PATH] == [
        (685, -510), (45, -420), (181, -571), (394, -738), (698, -792),
        (978, -746), (1067, -587), (1028, -403), (732, -117), (469, -107),
        (341, -225), (356, -417), (538, -576), (804, -742), (978, -742),
    ]


def test_all_six_tms_stained_glass_animations_have_distinct_scenes():
    proxy, _ = exporter.load_images()
    scenes = [
        scene for scene in exporter.SCENES
        if scene.key.startswith("stained-glass-")
    ]
    assert len(scenes) == 6
    assert [scene.marker_code for scene in scenes] == list(range(9, 15))
    for index, scene in enumerate(scenes):
        layers = exporter.scene_layers(proxy, exporter.arc.CanvasMaterializer(), scene)
        assert len(layers) == 1
        outlink = layers[0].frames[0][0].child("_outlink")
        assert outlink.value.startswith(
            f"Etc/_Canvas/BossLucid.img/StainedGlass/BreakEffect/{index}/"
        )


def test_lucid_field_effect_markers_are_argb4444_and_distinct():
    image = load_img(ROOT / "clien/Data/Map/Effect.img")
    signatures = set()
    for scene in exporter.SCENES:
        frame = image.root.get(
            f"customSkill/lucid/{scene.marker_name}/0"
        )
        assert isinstance(frame, WzCanvasProperty)
        assert (int(frame.width), int(frame.height)) == (7, 5)
        assert (int(frame.format), int(frame.format2)) == (1, 0)
        decoded = decode_canvas(frame, region="GMS").convert("RGBA")
        signature = tuple(decoded.getdata())[:5]
        decoded.close()
        assert signature == tuple(exporter.marker_pixels(scene.marker_code))[:5]
        signatures.add(signature)
    assert len(signatures) == len(exporter.SCENES)


def test_lucid_mushroom_is_materialized_for_the_legacy_client():
    image = load_img(ROOT / "clien/Data/Mob/8880164.img")
    assert [node.name for node in image.root.children()] == [
        "info", "regen", "stand", "move", "hit1", "die1"
    ]
    assert image.root.get("info/skill") is None
    canvases = []
    visible = 0

    def walk(node):
        yield node
        if hasattr(node, "children"):
            for child in node.children():
                yield from walk(child)

    for node in walk(image.root):
        if not isinstance(node, WzCanvasProperty):
            continue
        canvases.append(node)
        assert (int(node.format), int(node.format2)) == (1, 0)
        decoded = decode_canvas(node, region="GMS").convert("RGBA")
        visible += decoded.getbbox() is not None
        decoded.close()
    assert len(canvases) == 46
    assert visible == 46

    server = ET.parse(ROOT / "gms-server/wz/Mob.wz/8880164.img.xml").getroot()
    assert [child.get("name") for child in server if child.tag == "imgdir"] == [
        "info", "regen", "stand", "move", "hit1", "die1"
    ]
    for path in (
        ROOT / "gms-server/wz/String.wz/Mob.img.xml",
        ROOT / "gms-server/wz-zh-CN/String.wz/Mob.img.xml",
    ):
        root = ET.parse(path).getroot()
        name = root.find('./imgdir[@name="8880164"]/string[@name="name"]')
        assert name is not None and name.get("value") == "噩梦毒蘑菇"


def test_server_controller_covers_tms_lucid_mechanics_and_timing():
    source = (
        ROOT / "gms-server/src/main/java/org/gms/server/life/LucidBossCompat.java"
    ).read_text(encoding="utf-8")
    for mob_id in (8880140, 8880141, 8880142, 8880161, 8880164, 8880165, 8880171, 8880175):
        assert str(mob_id) in source
    for effect in (
        "dragonP1VideoLayer", "dragonP2VideoLayer", "laserRainVideoLayer",
        "phantomBarrageVideoLayer", "rushVideoLayer", "furyVideoLayer",
        "butterflyBurstVideoLayer", "bombVideoLayer", "stainedGlassVideoLayer",
        "stainedGlass1VideoLayer", "stainedGlass2VideoLayer",
        "stainedGlass3VideoLayer", "stainedGlass4VideoLayer",
        "stainedGlass5VideoLayer",
    ):
        assert effect in source
    for interval, count in ((5000, 5), (4500, 7), (4000, 10), (3000, 15), (2000, 20)):
        assert f"return {interval};" in source
        assert f"return {count};" in source
    assert "BUTTERFLY_CAPACITY = 40" in source
    assert "MAX_GOLEMS = 15" in source
    assert "nextStainedGlass = now + 10_000" in source
    assert "scheduleDamage(1260, 20, area, \"stained-glass\")" in source
    assert "FURY_LIMIT_MS = 45_000" in source
    assert "FURY_FAIL_DELAY_MS = FURY_LIMIT_MS + 4320" in source
    assert "scheduleDamage(4650, 100" in source
    assert "scheduleDamage(1260, 18" in source
    assert "PHANTOM_BARRAGE_PREPARE_MS = 2400" in source
    assert "PHANTOM_BARRAGE_HIT_INTERVAL_MS = 1000" in source
    assert "PHANTOM_BARRAGE_HIT_COUNT = 12" in source
    assert "(long) index * PHANTOM_BARRAGE_HIT_INTERVAL_MS" in source
    assert "RUSH_DURATION_MS = 3000" in source
    assert "RUSH_HIT_INTERVAL_MS = 100" in source
    assert "rushPositionAt(collisionTime)" in source
    assert "hitCharacters.add(character.getId())" in source
    assert 'scheduleDamage(3000, 20, null, "rush")' not in source
    assert "position.x - 20, position.y - 500, 40, 510" in source
    assert 'damageCharacter(character, 20, "hurdle-area")' in source
    assert "Lucid has summoned a powerful nightmare" in source
    assert "Lucid is gathering power" in source
    assert "applyFullMapDamage(100, \"fury-fail\")" in source
    assert "forceTeleport()" not in source
    assert "character.changeMap(map, destination)" not in source
    assert "skillId == 238" not in source
    assert "skillId == 201" not in source


def test_lucid_control_effects_have_boss_specific_cooldowns():
    compat = (
        ROOT / "gms-server/src/main/java/org/gms/server/life/LucidBossCompat.java"
    ).read_text(encoding="utf-8")
    monster = (
        ROOT / "gms-server/src/main/java/org/gms/server/life/Monster.java"
    ).read_text(encoding="utf-8")
    life_factory = (
        ROOT / "gms-server/src/main/java/org/gms/server/life/LifeFactory.java"
    ).read_text(encoding="utf-8")

    assert "CONTROL_EFFECT_COOLDOWN_MS = 60_000" in compat
    assert "mobId == LUCID_P3 && level == SEDUCE_P3_LEVEL" in compat
    assert "mobId == LUCID_P1 && attackPosition == 1" in compat
    assert "mobId == LUCID_P2 && attackPosition == 2" in compat
    assert "LucidBossCompat.skillCooldownMillis(" in monster
    assert "LucidBossCompat.usesAttackCooldown(getId(), attackPos)" in monster
    assert "LucidBossCompat.attackCooldownMillis(mid, i, coolTime)" in life_factory


def test_event_scripts_start_stop_and_transition_the_controller():
    for tree in ("gms-server/scripts", "gms-server/scripts-zh-CN"):
        source = (ROOT / tree / "event/LucidBattle.js").read_text(encoding="utf-8")
        assert "Java.type('org.gms.server.life.LucidBossCompat')" in source
        assert "LucidBossCompat.startPhase(phaseOneMap, phaseOneBoss, 1)" in source
        assert "LucidBossCompat.startPhase(targetMap, phaseTwoBoss, 2)" in source
        assert "mob.getId() == 8880142" in source
        assert "LucidBossCompat.startPhase(eim.getInstanceMap(phaseTwoMap), mob, 3)" in source
        assert source.count("stopLucidCompat(eim)") >= 3
        revive = source[
            source.index("function playerRevive"):
            source.index("function playerDisconnected")
        ]
        assert "player.enableActions();" in revive
        assert "reviveMap.movePlayer(player, reviveMap.getPortal(0).getPosition());" in revive
        assert "player.sendPacket(reviveMovement);" in revive


def test_unified_client_hook_routes_all_lucid_scene_markers():
    source = (
        ROOT / "tool/client-debug/karing-scene-compat/KaringSceneCompat.cpp"
    ).read_text(encoding="utf-8")
    assert "DetectLucidA4R4G4B4" in source
    assert "DetectLucidA8R8G8B8" in source
    assert "0xF124" in source
    assert "code >= 1 && code <= 14 ? 14 + code" in source
    assert "kMarkerCodeCount = 29" in source
    for code, scene in enumerate(exporter.SCENES, start=15):
        path = scene.output_name.replace("/", "\\")
        assert f'{{{code}, "Data\\\\Video\\\\{path}"}}' in source


def test_complete_projection_is_documented():
    text = (ROOT / "docs/migrations/lucid-expedition.md").read_text(encoding="utf-8")
    for term in (
        "LucidBossCompat", "Butterfly", "Dragon", "LaserRain", "Shoot",
        "RushLucid", "Fury", "8880164", "MCV",
    ):
        assert term in text


def main() -> int:
    tests = [
        value for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
    print(
        f"Lucid complete battle contract ok: tests={len(tests)} "
        f"scenes={len(exporter.SCENES)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Migrate TMS Wind Archer V/VI direct attacks into the empty 1312 book."""

from __future__ import annotations

import argparse
import html
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import patch_blaze_wizard_v_vi as engine


ROOT = Path(__file__).resolve().parents[3]
TMS_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
MS_EXPORT_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-MS-Export/WindArcher")
SOURCE_PATHS = {
    "1314": TMS_ROOT / "Skill" / "_Canvas" / "1314.img",
    "40003": TMS_ROOT / "Skill" / "_Canvas" / "40003.img",
}
SECOND_ATOM_CANVAS = TMS_ROOT / "Etc" / "_Canvas" / "SecondAtom.img"
SECOND_ATOM_METADATA = TMS_ROOT / "Etc" / "SecondAtom.img"
SECOND_ATOM_PROJECTILES = {
    13121003: (79, 8),
    13121015: (47, 9),
    13121016: (48, 9),
    13121017: (49, 13),
    13121018: (79, 8),
}
CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "1312.img"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
CLIENT_MAP_EFFECT = ROOT / "clien" / "Data" / "Map" / "Effect.img"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "1312.img.xml"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"
FIELD_EFFECT_ROOT = "customSkill/windArcher"
VIDEO_MARKERS = ("monsoonVideoLayer", "mistralSpringVideoLayer", "elementalTempestVideoLayer")
MASTER_LEVEL = 30
CUSTOM_SKILL_IDS = range(13121000, 13121024)

SkillSpec = engine.SkillSpec


# Values are the evaluated TMS level-30 common parameters. Hidden entries are
# packet-addressable attack stages and do not appear in the legacy skill panel.
SKILLS = (
    SkillSpec(13121003, 400031022, "40003", "风转奇想", 925, 5, 1, 500, 0, False,
              lt=(-650, -450), rb=(650, 250), duration_seconds=8),
    SkillSpec(13121004, 400031030, "40003", "西尔芙之壁", 935, 5, 3, 1000, 0, False,
              effect_nodes=(), include_hit=False,
              extra_nodes=("repeat", "special"),
              lt=(-500, -450), rb=(500, 150), duration_seconds=30),
    SkillSpec(13121005, 400031031, "40003", "西尔芙之壁：旋风", 935, 5, 3,
              icon_source_id=400031030, effect_nodes=(),
              lt=(-500, -450), rb=(500, 150)),
    SkillSpec(13121009, 13141004, "1314", "妖精护盾VI", 625, 5, 7, 42, 0, False,
              lt=(-430, -240), rb=(50, 85)),
    SkillSpec(13121010, 13141005, "1314", "季风VI", 705, 12, 15, 410, 0, False,
              extra_nodes=("mob",), lt=(-550, -330), rb=(550, 300)),
    SkillSpec(13121011, 13141007, "1314", "阿涅摩伊", 1733, 15, 12, 41, 0, False,
              lt=(-480, -430), rb=(480, 100), duration_seconds=20),
    SkillSpec(13121012, 13141008, "1314", "阿涅摩伊：强风", 1879, 10, 10,
              icon_source_id=13141007, effect_nodes=(),
              lt=(-520, -280), rb=(50, 80)),

    SkillSpec(13121013, 13141500, "1314", "风之圣谕", 1670, 10, 15, 1200, 10, False,
              effect_nodes=(), lt=(-1200, -800), rb=(1200, 800), duration_seconds=20),
    SkillSpec(13121014, 13141500, "1314", "风之圣谕：风之刃", 1670, 10, 15,
              icon_source_id=13141500, effect_nodes=(),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(13121015, 13141502, "1314", "风之圣谕：精灵气息", 1320, 5, 1,
              icon_source_id=13141500, effect_nodes=(),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(13121016, 13141503, "1314", "风之圣谕：欢快精灵气息", 1440, 6, 1,
              icon_source_id=13141500, effect_nodes=(),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(13121017, 13141504, "1314", "风之圣谕：猛烈精灵气息", 1275, 7, 1,
              icon_source_id=13141500, effect_nodes=(),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(13121018, 400031022, "40003", "风转奇想：精灵气息", 925, 5, 1,
              icon_source_id=400031022, effect_nodes=(),
              lt=(-650, -450), rb=(650, 250)),

    SkillSpec(13121019, 13141506, "1314", "元素风暴", 8027, 12, 15, 1000, 10, False,
              effect_nodes=("effect", "effect0", "effect2"),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(13121020, 13141507, "1314", "元素风暴：箭雨", 8204, 15, 15,
              icon_source_id=13141506, effect_nodes=(),
              lt=(-1200, -800), rb=(1200, 800)),
    SkillSpec(13121023, 13141506, "1314", "元素风暴：风之波动", 8027, 12, 15,
              icon_source_id=13141506, effect_nodes=(),
              lt=(-1200, -800), rb=(1200, 800)),
)

TIMED_EFFECTS = {}

VISIBLE_IDS = {spec.target_id for spec in SKILLS if not spec.hidden}
AREA_ATTACK_IDS = {spec.target_id for spec in SKILLS if spec.mob_count > 1}
SOURCE_BULLET_COUNTS = {
    13121003: 10,
    13121015: 1,
    13121016: 1,
    13121017: 1,
}
LEVEL_EXTRA_VALUES = {
    13121003: {
        "x": 10,
        "w": 15,
        "dot": 1100,
        "dotTime": 9,
        "dotInterval": 1,
    },
    13121004: {
        "y": 0,
        "w": 300,
        "z": 1,
        "dot": 935,
        "s": 50,
        "q": 5,
        "q2": 3,
        "w2": 2,
    },
    13121005: {"x": 50},
    13121009: {"x": 300},
}


def configure_engine() -> None:
    engine.TMS_ROOT = TMS_ROOT
    engine.MS_EXPORT_ROOT = MS_EXPORT_ROOT
    engine.SOURCE_PATHS = SOURCE_PATHS
    engine.CLIENT_SKILL = CLIENT_SKILL
    engine.CLIENT_STRING = CLIENT_STRING
    engine.CLIENT_MAP_EFFECT = CLIENT_MAP_EFFECT
    engine.SERVER_SKILL = SERVER_SKILL
    engine.SERVER_STRING = SERVER_STRING
    engine.FIELD_EFFECT_ROOT = FIELD_EFFECT_ROOT
    engine.VIDEO_MARKERS = VIDEO_MARKERS
    engine.MASTER_LEVEL = MASTER_LEVEL
    engine.CUSTOM_SKILL_IDS = CUSTOM_SKILL_IDS
    engine.SKILLS = SKILLS
    engine.TIMED_EFFECTS = TIMED_EFFECTS
    engine.base.SKILLS = SKILLS
    engine.base.MS_EXPORT_ROOT = MS_EXPORT_ROOT


def backup(path: Path) -> None:
    target = path.with_name(path.name + ".bak-wind-archer-v-vi")
    if not target.exists():
        shutil.copy2(path, target)
        print(f"backup: {target}")


def add_second_atom_projectile(target, key, atom_index: int,
                               expected_frame_count: int) -> None:
    canvas_root = engine.WzImage.from_bytes(
        SECOND_ATOM_CANVAS.read_bytes(),
        key=engine.WzKey.for_region("BMS"),
        name=SECOND_ATOM_CANVAS.name,
    ).parse()
    metadata_root = engine.WzImage.from_bytes(
        SECOND_ATOM_METADATA.read_bytes(),
        key=engine.WzKey.for_region("BMS"),
        name=SECOND_ATOM_METADATA.name,
    ).parse()
    source = canvas_root.get(
        f"atom/{atom_index}/layer/parentAtom"
    )
    metadata = metadata_root.get(
        f"atom/{atom_index}/layer/parentAtom"
    )
    source_frames = engine.base.numeric_canvases(source)
    if (not isinstance(metadata, engine.WzSubProperty)
            or len(source_frames) != expected_frame_count):
        raise RuntimeError(
            f"SecondAtom {atom_index} flight animation mismatch"
        )

    ball = engine.WzSubProperty("ball", target)
    for source_frame in source_frames:
        frame_metadata = metadata.get(source_frame.name)
        if not isinstance(frame_metadata, engine.WzCanvasProperty):
            raise RuntimeError(
                f"missing SecondAtom {atom_index} projectile metadata: {source_frame.name}"
            )
        origin = frame_metadata.get("origin")
        delay = frame_metadata.get("delay")
        z = frame_metadata.get("z")
        if origin is None or delay is None or z is None:
            raise RuntimeError(
                f"incomplete SecondAtom {atom_index} projectile metadata: {source_frame.name}"
            )
        encoded = engine.base.encode_target_canvas(
            source_frame, source_frame.name, ball, key
        )
        engine.set_vector(encoded, "origin", (int(origin.x), int(origin.y)))
        engine.set_int(encoded, "delay", int(delay.value))
        engine.set_int(encoded, "z", int(z.value))
        ball.add(encoded)
    engine.base.replace_child(target, ball)

    # The old ranged branch resolves custom projectiles most reliably from
    # the evaluated level node. Keep one top-level animation as the source.
    for level in range(1, MASTER_LEVEL + 1):
        level_node = target.get(f"level/{level}")
        if not isinstance(level_node, engine.WzSubProperty):
            raise RuntimeError(f"missing SecondAtom {atom_index} level: {level}")
        engine.base.replace_child(
            level_node, engine.WzUolProperty("ball", "../../ball", level_node)
        )


def source_layer_timeline(groups, metadata, skill_id: int, node_name: str):
    meta = metadata.roots[skill_id]
    for segment in node_name.split("/"):
        meta = metadata.child(meta, segment)
    frames = engine.base.ms_numeric_frames(meta, metadata)
    if not frames:
        raise RuntimeError(f"missing source animation metadata: {skill_id}/{node_name}")
    elapsed = 0
    timeline = []
    for frame_meta in frames:
        delay = engine.base.ms_int(frame_meta, "delay", 60) or 60
        canvas = engine.base.resolve_ms_canvas(frame_meta, groups, metadata)
        timeline.append((elapsed, elapsed + delay, canvas, frame_meta))
        elapsed += delay
    return timeline


def replace_time_aligned_effect(target, key, groups, metadata,
                                skill_id: int, layer_names: tuple[str, ...]) -> None:
    timelines = [
        source_layer_timeline(groups, metadata, skill_id, name)
        for name in layer_names
    ]
    boundaries = sorted({
        time
        for timeline in timelines
        for begin, end, _canvas, _meta in timeline
        for time in (begin, end)
    })
    effect = engine.WzSubProperty("effect", target)
    for begin, end in zip(boundaries, boundaries[1:]):
        active = []
        for timeline in timelines:
            segment = next(
                (item for item in timeline if item[0] <= begin < item[1]), None
            )
            if segment is not None and segment[2] is not None:
                active.append((segment[2], segment[3]))
        frame_name = str(len(engine.base.numeric_canvases(effect)))
        if not active:
            transparent = engine.base.Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            frame = engine.WzCanvasProperty(frame_name, effect)
            frame.width = 1
            frame.height = 1
            frame.format = engine.base.CANVAS_FORMAT
            frame.format2 = 0
            frame._png_data = engine.base.encode_canvas_payload(
                transparent, engine.base.CANVAS_FORMAT, 1, 1,
                key=key, listwz=False, zlib_level=9
            )
            frame._png_length = len(frame._png_data)
            engine.set_vector(frame, "origin", (0, 0))
        elif len(active) == 1:
            frame = engine.base.encode_target_canvas(
                active[0][0], frame_name, effect, key, meta=active[0][1]
            )
        else:
            canvases = [item[0] for item in active]
            metas = [item[1] for item in active]
            images = [
                engine.base.clean_rgba(engine.base.decode_source_canvas(canvas))
                for canvas in canvases
            ]
            origins = [
                engine.base.canvas_origin(canvas, meta)
                for canvas, meta in zip(canvases, metas)
            ]
            left = min(-origin[0] for origin in origins)
            top = min(-origin[1] for origin in origins)
            right = max(
                image.width - origin[0]
                for image, origin in zip(images, origins)
            )
            bottom = max(
                image.height - origin[1]
                for image, origin in zip(images, origins)
            )
            merged = engine.base.Image.new(
                "RGBA", (max(1, right - left), max(1, bottom - top)),
                (0, 0, 0, 0)
            )
            for image, origin in zip(images, origins):
                merged.alpha_composite(
                    image, (-origin[0] - left, -origin[1] - top)
                )
            width, height, scale = engine.base.fit_size(
                merged.width, merged.height
            )
            if (width, height) != merged.size:
                merged = merged.resize(
                    (width, height), engine.base.Image.Resampling.LANCZOS
                )
            frame = engine.WzCanvasProperty(frame_name, effect)
            frame.width = width
            frame.height = height
            frame.format = engine.base.CANVAS_FORMAT
            frame.format2 = 0
            frame._png_data = engine.base.encode_canvas_payload(
                merged, engine.base.CANVAS_FORMAT, width, height,
                key=key, listwz=False, zlib_level=9
            )
            frame._png_length = len(frame._png_data)
            engine.set_vector(
                frame, "origin", (round(-left * scale), round(-top * scale))
            )
        engine.set_int(frame, "delay", end - begin)
        effect.add(frame)
    engine.base.replace_child(target, effect)


def set_hit_variant_metadata(target, *, random_hit: int | None = None,
                             random_origin: int | None = None,
                             random_angle: int | None = None,
                             use_z: int | None = None,
                             z: int | None = None) -> None:
    hit = target.get("hit")
    variant = target.get("hit/0")
    if not isinstance(hit, engine.WzSubProperty) or not isinstance(
            variant, engine.WzSubProperty):
        raise RuntimeError(f"missing hit animation: {target.name}")
    if random_hit is not None:
        engine.set_int(hit, "randomHit", random_hit)
    for name, value in (
        ("randomHitOrigin", random_origin),
        ("randomHitAngle", random_angle),
        ("useZ", use_z),
        ("z", z),
    ):
        if value is not None:
            engine.set_int(variant, name, value)


def set_barrier_loop_metadata(target) -> None:
    for node_name in ("repeat", "special"):
        node = target.get(node_name)
        if not isinstance(node, engine.WzSubProperty):
            raise RuntimeError(f"missing Gale Barrier {node_name}")
        for variant in node.children():
            if isinstance(variant, engine.WzSubProperty) and variant.name.isdigit():
                engine.set_int(variant, "z", 2)


def build_skill(spec, parent, key, groups, metadata):
    target = engine.build_skill_original(spec, parent, key, groups, metadata)
    projectile = SECOND_ATOM_PROJECTILES.get(spec.target_id)
    if projectile is not None:
        add_second_atom_projectile(target, key, *projectile)
    if spec.target_id == 13121004:
        replace_time_aligned_effect(
            target, key, groups, metadata, 400031030, ("effect0", "effect")
        )
        set_barrier_loop_metadata(target)
    elif spec.target_id == 13121005:
        replace_time_aligned_effect(
            target, key, groups, metadata, 400031031, ("effect0", "effect")
        )
        set_hit_variant_metadata(target, random_hit=1, random_origin=20)
    elif spec.target_id == 13121009:
        set_hit_variant_metadata(
            target, random_origin=35, random_angle=1, use_z=1, z=1
        )
    elif spec.target_id in (13121015, 13121016, 13121017):
        set_hit_variant_metadata(
            target, random_origin=45, random_angle=1, use_z=1, z=1
        )
    elif spec.target_id == 13121012:
        replace_time_aligned_effect(
            target, key, groups, metadata, 13141008,
            ("special", "summon/summoned")
        )
    elif spec.target_id == 13121019:
        replace_time_aligned_effect(
            target, key, groups, metadata, 13141506,
            ("effect", "effect0", "effect2")
        )
    action = target.child("action")
    engine.set_string(action, "0", "windshot")
    if spec.target_id in AREA_ATTACK_IDS:
        info = engine.WzSubProperty("info", target)
        engine.set_int(info, "type", 1)
        engine.set_int(info, "areaAttack", 1)
        engine.base.replace_child(target, info)
    engine.set_string(target, "elemAttr", "i")
    engine.set_int(target, "weapon", 45)
    for level in range(1, MASTER_LEVEL + 1):
        level_node = target.get(f"level/{level}")
        bullet_count = SOURCE_BULLET_COUNTS.get(
            spec.target_id, min(15, max(1, spec.attack_count))
        )
        engine.set_int(level_node, "bulletCount", bullet_count)
        for name, value in LEVEL_EXTRA_VALUES.get(spec.target_id, {}).items():
            engine.set_int(level_node, name, value)
    return target


def level_text(spec) -> str:
    if spec.target_id == 13121003:
        return ("消耗MP 500，形成10个最多存在8秒并独立寻找敌人的妖精气息，"
                "每个以925%伤害攻击5次；多个气息命中同一怪物时，第2个起最终伤害减少15%；"
                "命中后9秒内每1秒造成1100%持续伤害                    ")
    cooldown = f"，冷却时间{spec.cooldown}秒" if spec.cooldown else ""
    duration = f"，持续{spec.duration_seconds}秒" if spec.duration_seconds else ""
    return (f"消耗MP {spec.mp_con}，最多攻击{spec.mob_count}名敌人，"
            f"以{spec.damage}%伤害攻击{spec.attack_count}次{duration}{cooldown}                    ")


def server_skill_block(spec) -> str:
    lines = [f'  <imgdir name="{spec.target_id}">', '    <imgdir name="action">',
             '      <string name="0" value="windshot"/>', "    </imgdir>",
             '    <imgdir name="level">']
    for level in range(1, MASTER_LEVEL + 1):
        lines.extend([
            f'      <imgdir name="{level}">',
            f'        <int name="attackCount" value="{min(15, spec.attack_count)}"/>',
            f'        <int name="bulletCount" value="{SOURCE_BULLET_COUNTS.get(spec.target_id, min(15, max(1, spec.attack_count)))}"/>',
            f'        <int name="cooltime" value="{spec.cooldown}"/>',
            f'        <int name="damage" value="{spec.damage}"/>',
            f'        <string name="hs" value="h{level}"/>',
            f'        <vector name="lt" x="{spec.lt[0]}" y="{spec.lt[1]}"/>',
            f'        <int name="mobCount" value="{min(15, spec.mob_count)}"/>',
            f'        <int name="mpCon" value="{spec.mp_con}"/>',
            f'        <vector name="rb" x="{spec.rb[0]}" y="{spec.rb[1]}"/>',
            *(f'        <int name="{name}" value="{value}"/>'
              for name, value in LEVEL_EXTRA_VALUES.get(spec.target_id, {}).items()),
            *([f'        <int name="time" value="{spec.duration_seconds}"/>']
              if spec.duration_seconds is not None else []),
            "      </imgdir>",
        ])
    lines.extend(["    </imgdir>", f'    <int name="masterLevel" value="{MASTER_LEVEL}"/>',
                  '    <string name="elemAttr" value="i"/>', '    <int name="weapon" value="45"/>'])
    if spec.target_id in AREA_ATTACK_IDS:
        lines.extend(['    <imgdir name="info">', '      <int name="type" value="1"/>',
                      '      <int name="areaAttack" value="1"/>', '    </imgdir>'])
    if spec.hidden:
        lines.append('    <int name="invisible" value="1"/>')
    lines.append("  </imgdir>")
    return "\n".join(lines)


def patch_server_skill(dry_run: bool) -> None:
    text = SERVER_SKILL.read_text(encoding="utf-8")
    info_start, info_end = engine.find_imgdir_block(text, "info")
    info = text[info_start:info_end]
    blocks = "\n".join(server_skill_block(spec) for spec in SKILLS)
    updated = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
               f'<imgdir name="1312.img">\n{info}\n<imgdir name="skill">\n'
               f'{blocks}\n</imgdir>\n</imgdir>\n')
    if not dry_run:
        backup(SERVER_SKILL)
        engine.base.atomic_write_text(SERVER_SKILL, updated)


def patch_client_string(strings, dry_run: bool) -> None:
    image = engine.WzImage.from_bytes(
        CLIENT_STRING.read_bytes(), key=engine.WzKey.for_region("GMS"), name=CLIENT_STRING.name
    )
    root = image.parse()
    for skill_id in CUSTOM_SKILL_IDS:
        root._children.pop(str(skill_id), None)
    for spec in SKILLS:
        source = engine.source_string_values(strings, spec.source_id)
        node = engine.WzSubProperty(str(spec.target_id), root)
        engine.set_string(node, "name", spec.name)
        engine.set_string(node, "desc", source.get("desc", "TMS风灵使者五/六转攻击技能兼容迁移。"))
        for level in range(1, MASTER_LEVEL + 1):
            engine.set_string(node, f"h{level}", level_text(spec))
        engine.base.replace_child(root, node)
    if not dry_run:
        backup(CLIENT_STRING)
        engine.base.atomic_write_bytes(CLIENT_STRING, engine.encode_image_body(image, image.wz_file.reader))


def server_string_block(spec, source: dict[str, str]) -> str:
    lines = [f'<imgdir name="{spec.target_id}">',
             f'  <string name="name" value="{html.escape(spec.name, quote=True)}"/>',
             f'  <string name="desc" value="{html.escape(source.get("desc", "TMS风灵使者五/六转攻击技能兼容迁移。"), quote=True)}"/>']
    for level in range(1, MASTER_LEVEL + 1):
        lines.append(f'  <string name="h{level}" value="{html.escape(level_text(spec), quote=True)}"/>')
    lines.append("</imgdir>")
    return "\n".join(lines)


def validate() -> None:
    image = engine.WzImage.from_bytes(
        CLIENT_SKILL.read_bytes(), key=engine.WzKey.for_region("GMS"), name=CLIENT_SKILL.name
    )
    root = image.parse()
    actual = {
        int(child.name) for child in root.get("skill").children()
        if child.name.isdigit() and int(child.name) in CUSTOM_SKILL_IDS
    }
    expected = {spec.target_id for spec in SKILLS}
    if actual != expected:
        raise RuntimeError(f"Wind Archer skill mismatch: missing={sorted(expected-actual)} extra={sorted(actual-expected)}")
    barrier = root.get("skill/13121004")
    tornado = root.get("skill/13121005")
    if barrier.get("hit") is not None:
        raise RuntimeError("Gale Barrier cast must not replay the tornado hit effect")
    barrier_effect = engine.base.numeric_canvases(barrier.get("effect"))
    tornado_effect = engine.base.numeric_canvases(tornado.get("effect"))
    tornado_hit = engine.base.numeric_canvases(tornado.get("hit/0"))
    if (len(barrier_effect) != 13 or
            sum(engine.base.frame_delay(frame) for frame in barrier_effect) != 1170 or
            any(engine.base.frame_delay(frame) != 90 for frame in barrier_effect)):
        raise RuntimeError("Gale Barrier cast effect timeline mismatch")
    if (len(tornado_effect) != 12 or
            sum(engine.base.frame_delay(frame) for frame in tornado_effect) != 1080 or
            any(engine.base.frame_delay(frame) != 90 for frame in tornado_effect)):
        raise RuntimeError("Gale Barrier tornado effect timeline mismatch")
    if len(tornado_hit) != 6 or sum(engine.base.frame_delay(frame) for frame in tornado_hit) != 540:
        raise RuntimeError("Gale Barrier tornado hit timeline mismatch")
    random_hit = tornado.get("hit/randomHit")
    random_origin = tornado.get("hit/0/randomHitOrigin")
    if random_hit is None or int(random_hit.value) != 1:
        raise RuntimeError("Gale Barrier tornado randomHit mismatch")
    if random_origin is None or int(random_origin.value) != 20:
        raise RuntimeError("Gale Barrier tornado randomHitOrigin mismatch")
    for node_name, expected_frame_count, expected_duration in (
            ("repeat", 12, 360), ("special", 4, 360)):
        node = barrier.get(node_name)
        variants = node.children() if isinstance(node, engine.WzSubProperty) else []
        if len(variants) != 3:
            raise RuntimeError(f"Gale Barrier {node_name} variant mismatch")
        for variant in variants:
            frames = engine.base.numeric_canvases(variant)
            variant_z = variant.get("z")
            if (len(frames) != expected_frame_count or
                    sum(engine.base.frame_delay(frame) for frame in frames) != expected_duration or
                    variant_z is None or int(variant_z.value) != 2):
                raise RuntimeError(
                    f"Gale Barrier {node_name} timeline mismatch: {variant.name}"
                )
    fairy_spiral = root.get("skill/13121009")
    fairy_effect = engine.base.numeric_canvases(fairy_spiral.get("effect"))
    fairy_hit = engine.base.numeric_canvases(fairy_spiral.get("hit/0"))
    if (len(fairy_effect) != 11 or
            sum(engine.base.frame_delay(frame) for frame in fairy_effect) != 990):
        raise RuntimeError("Fairy Spiral VI effect timeline mismatch")
    if (len(fairy_hit) != 8 or
            sum(engine.base.frame_delay(frame) for frame in fairy_hit) != 480):
        raise RuntimeError("Fairy Spiral VI hit timeline mismatch")
    for path, expected_value in {
        "hit/0/randomHitOrigin": 35,
        "hit/0/randomHitAngle": 1,
        "hit/0/useZ": 1,
        "hit/0/z": 1,
    }.items():
        value = fairy_spiral.get(path)
        if value is None or int(value.value) != expected_value:
            raise RuntimeError(f"Fairy Spiral VI hit metadata mismatch: {path}")
    monsoon_mob = engine.base.numeric_canvases(root.get("skill/13121010/mob/0"))
    if (len(monsoon_mob) != 6
            or sum(engine.base.frame_delay(frame) for frame in monsoon_mob) != 720):
        raise RuntimeError("Monsoon VI mob effect timeline mismatch")
    anemoi_effect = engine.base.numeric_canvases(root.get("skill/13121012/effect"))
    if (len(anemoi_effect) != 15
            or sum(engine.base.frame_delay(frame) for frame in anemoi_effect) != 810):
        raise RuntimeError("Anemoi gale effect timeline mismatch")
    elemental_effect = engine.base.numeric_canvases(root.get("skill/13121019/effect"))
    if (len(elemental_effect) != 20
            or sum(engine.base.frame_delay(frame) for frame in elemental_effect) != 3180):
        raise RuntimeError("Elemental Tempest effect timeline mismatch")
    projectile = root.get("skill/13121003/ball")
    projectile_frames = engine.base.numeric_canvases(projectile)
    projectile_sizes = [(int(frame.width), int(frame.height)) for frame in projectile_frames]
    expected_projectile_sizes = [
        (240, 72), (288, 72), (276, 72), (288, 72),
        (244, 72), (208, 72), (264, 72), (272, 72),
    ]
    expected_projectile_origins = [
        (108, 34), (147, 34), (134, 34), (153, 34),
        (104, 34), (60, 34), (114, 34), (131, 34),
    ]
    if projectile_sizes != expected_projectile_sizes:
        raise RuntimeError(f"Merciless Winds projectile size mismatch: {projectile_sizes}")
    for index, (frame, expected_origin) in enumerate(
            zip(projectile_frames, expected_projectile_origins)):
        origin = frame.get("origin")
        delay = frame.get("delay")
        z = frame.get("z")
        if (int(origin.x), int(origin.y)) != expected_origin:
            raise RuntimeError(f"Merciless Winds projectile origin mismatch: {index}")
        if int(delay.value) != 60 or int(z.value) != 0:
            raise RuntimeError(f"Merciless Winds projectile timing mismatch: {index}")
        if int(frame.format) != 1 or int(frame.format2) != 0:
            raise RuntimeError(f"Merciless Winds projectile format mismatch: {index}")
    for skill_id, (atom_index, frame_count) in SECOND_ATOM_PROJECTILES.items():
        frames = engine.base.numeric_canvases(root.get(f"skill/{skill_id}/ball"))
        if (len(frames) != frame_count
                or sum(engine.base.frame_delay(frame) for frame in frames)
                    != frame_count * 60):
            raise RuntimeError(
                f"SecondAtom {atom_index} projectile timeline mismatch"
            )
        for level in range(1, MASTER_LEVEL + 1):
            ball = root.get(f"skill/{skill_id}/level/{level}/ball")
            if not isinstance(ball, engine.WzUolProperty) or ball.value != "../../ball":
                raise RuntimeError(
                    f"SecondAtom {atom_index} projectile link mismatch: {level}"
                )
    for skill_id in (13121015, 13121016, 13121017):
        hit_frames = engine.base.numeric_canvases(root.get(f"skill/{skill_id}/hit/0"))
        if (len(hit_frames) != 8
                or sum(engine.base.frame_delay(frame) for frame in hit_frames) != 480):
            raise RuntimeError(f"Mistral spirit hit timeline mismatch: {skill_id}")
        for path, expected_value in {
            "hit/0/randomHitOrigin": 45,
            "hit/0/randomHitAngle": 1,
            "hit/0/useZ": 1,
            "hit/0/z": 1,
        }.items():
            value = root.get(f"skill/{skill_id}/{path}")
            if value is None or int(value.value) != expected_value:
                raise RuntimeError(
                    f"Mistral spirit hit metadata mismatch: {skill_id}/{path}"
                )
    for spec in SKILLS:
        if (spec.target_id not in SECOND_ATOM_PROJECTILES
                and root.get(f"skill/{spec.target_id}/ball") is not None):
            raise RuntimeError(f"unexpected projectile animation: {spec.target_id}")
    canvas_count = 0
    for spec in SKILLS:
        node = root.get(f"skill/{spec.target_id}")
        if not isinstance(node, engine.WzSubProperty):
            raise RuntimeError(f"missing client skill {spec.target_id}")
        action = node.get("action/0")
        if action is None or action.value != "windshot":
            raise RuntimeError(f"action mismatch {spec.target_id}")
        level = node.get(f"level/{MASTER_LEVEL}")
        values = (int(level.get("damage").value), int(level.get("attackCount").value),
                  int(level.get("mobCount").value), int(level.get("mpCon").value),
                  int(level.get("cooltime").value))
        expected_values = (spec.damage, spec.attack_count, spec.mob_count, spec.mp_con, spec.cooldown)
        if values != expected_values:
            raise RuntimeError(f"attack parameter mismatch {spec.target_id}: {values}")
        bullet_count = level.get("bulletCount")
        expected_bullet_count = SOURCE_BULLET_COUNTS.get(
            spec.target_id, min(15, max(1, spec.attack_count))
        )
        if bullet_count is None or int(bullet_count.value) != expected_bullet_count:
            raise RuntimeError(f"bullet count mismatch {spec.target_id}")
        invisible = node.get("invisible")
        if spec.hidden != (invisible is not None and int(invisible.value) == 1):
            raise RuntimeError(f"visibility mismatch {spec.target_id}")
        for name, expected_value in LEVEL_EXTRA_VALUES.get(spec.target_id, {}).items():
            value = level.get(name)
            if value is None or int(value.value) != expected_value:
                raise RuntimeError(
                    f"extra parameter mismatch {spec.target_id}/{name}"
                )
        if spec.duration_seconds is not None:
            duration = level.get("time")
            if duration is None or int(duration.value) != spec.duration_seconds:
                raise RuntimeError(f"duration mismatch {spec.target_id}")
        lt = level.get("lt")
        rb = level.get("rb")
        if (int(lt.x), int(lt.y), int(rb.x), int(rb.y)) != (*spec.lt, *spec.rb):
            raise RuntimeError(f"range mismatch {spec.target_id}")
        stack = [node]
        while stack:
            current = stack.pop()
            if isinstance(current, engine.WzCanvasProperty):
                canvas_count += 1
                if int(current.format) != 1 or int(current.format2) != 0:
                    raise RuntimeError(f"non-ARGB4444 Canvas in {spec.target_id}")
                if int(current.width) > 1280 or int(current.height) > 720:
                    raise RuntimeError(f"oversized Canvas in {spec.target_id}: {current.width}x{current.height}")
            if hasattr(current, "children"):
                stack.extend(current.children())
    effect_image = engine.WzImage.from_bytes(
        CLIENT_MAP_EFFECT.read_bytes(), key=engine.WzKey.for_region("GMS"),
        name=CLIENT_MAP_EFFECT.name,
    ).parse()
    for marker_name in VIDEO_MARKERS:
        marker = effect_image.get(f"{FIELD_EFFECT_ROOT}/{marker_name}/0")
        if not isinstance(marker, engine.WzCanvasProperty) or (int(marker.width), int(marker.height)) != (7, 5):
            raise RuntimeError(f"missing MCV marker: {marker_name}")
    server_root = ET.parse(SERVER_SKILL).getroot()
    server_skills = server_root.find("./imgdir[@name='skill']")
    if server_skills is None:
        raise RuntimeError("missing server skill root")
    for spec in SKILLS:
        server_node = server_skills.find(f"./imgdir[@name='{spec.target_id}']")
        if server_node is None:
            raise RuntimeError(f"missing server skill {spec.target_id}")
        action = server_node.find("./imgdir[@name='action']/string[@name='0']")
        if action is None or action.get("value") != "windshot":
            raise RuntimeError(f"server action mismatch {spec.target_id}")
        server_level = server_node.find(f"./imgdir[@name='level']/imgdir[@name='{MASTER_LEVEL}']")
        cooldown = server_level.find("./int[@name='cooltime']") if server_level is not None else None
        if cooldown is None or int(cooldown.get("value")) != spec.cooldown:
            raise RuntimeError(f"server cooldown mismatch {spec.target_id}")
        server_bullet_count = server_level.find("./int[@name='bulletCount']")
        expected_bullet_count = SOURCE_BULLET_COUNTS.get(
            spec.target_id, min(15, max(1, spec.attack_count))
        )
        if (server_bullet_count is None
                or int(server_bullet_count.get("value")) != expected_bullet_count):
            raise RuntimeError(f"server bullet count mismatch {spec.target_id}")
        server_invisible = server_node.find("./int[@name='invisible']")
        if spec.hidden != (
                server_invisible is not None
                and int(server_invisible.get("value")) == 1
        ):
            raise RuntimeError(f"server visibility mismatch {spec.target_id}")
        for name, expected_value in LEVEL_EXTRA_VALUES.get(spec.target_id, {}).items():
            value = server_level.find(f"./int[@name='{name}']")
            if value is None or int(value.get("value")) != expected_value:
                raise RuntimeError(f"server extra parameter mismatch {spec.target_id}/{name}")
        if spec.duration_seconds is not None:
            duration = server_level.find("./int[@name='time']")
            if duration is None or int(duration.get("value")) != spec.duration_seconds:
                raise RuntimeError(f"server duration mismatch {spec.target_id}")
    print(f"validated Wind Archer V/VI resources: skills={len(SKILLS)} canvases={canvas_count}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    configure_engine()
    if args.validate_only:
        validate()
        return 0
    groups, strings, metadata = engine.load_sources()
    engine.patch_client_skill(groups, metadata, args.dry_run)
    patch_client_string(strings, args.dry_run)
    patch_server_skill(args.dry_run)
    engine.patch_server_string(strings, args.dry_run)
    engine.patch_map_effect(args.dry_run)
    if not args.dry_run:
        validate()
    return 0


configure_engine()
engine.backup = backup
engine.build_skill_original = engine.build_skill
engine.build_skill = build_skill
engine.level_text = level_text
engine.server_skill_block = server_skill_block
engine.patch_server_skill = patch_server_skill
engine.patch_client_string = patch_client_string
engine.server_string_block = server_string_block


if __name__ == "__main__":
    raise SystemExit(main())

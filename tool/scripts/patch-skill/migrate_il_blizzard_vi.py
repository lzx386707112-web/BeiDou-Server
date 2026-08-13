#!/usr/bin/env python3
"""Incrementally migrate the validated Ice/Lightning V/VI skill batches."""

from __future__ import annotations

import io
import os
import re
import sys
import zipfile
from dataclasses import replace
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
WZPY = ROOT / "tool" / "wz-python"
sys.path[:0] = [str(PATCH_SKILL), str(WZPY)]

import patch_explorer_other_v_vi as migration  # noqa: E402
import retire_il_archmage_v_vi as retire  # noqa: E402
from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzSubProperty  # noqa: E402
from wzpy.writer import (  # noqa: E402
    _encode_property_list,
    encode_compressed_int,
    re_encrypt_string,
)


FREEZING_BREATH_SOURCE_ID = 2221011
FREEZING_BREATH_TARGET_ID = 2221009
REMOVED_ICE_AGE_TICK_TARGET_ID = 2221013
FALLING_SOURCE_ID = 400021030
FALLING_TARGET_ID = 2221010
FALLING_FIRST_SOURCE_ID = 400021031
FALLING_FIRST_TARGET_ID = 2221011
FALLING_SECOND_SOURCE_ID = 400021040
FALLING_SECOND_TARGET_ID = 2221012
CHAIN_SOURCE_ID = 2241000
CHAIN_TARGET_ID = 2221017
CHAIN_FIELD_SOURCE_ID = 2241001
CHAIN_FIELD_TARGET_ID = 2221018
CHAIN_FIELD_TICK_TARGET_ID = 2221019
MAIN_SOURCE_ID = 2241003
MAIN_TARGET_ID = 2221020
PASSIVE_SOURCE_ID = 2241004
PASSIVE_TARGET_ID = 2221021
FROZEN_LIGHTNING_SOURCE_ID = 2241500
FROZEN_LIGHTNING_TARGET_ID = 2221027
FROZEN_LIGHTNING_FIELD_SOURCE_ID = 2241501
FROZEN_LIGHTNING_FIELD_TARGET_ID = 2221028
FROZEN_LIGHTNING_ERUPTION_SOURCE_ID = 2241503
FROZEN_LIGHTNING_ERUPTION_TARGET_ID = 2221029
PARABOLIC_VOLT_SOURCE_ID = 2241505
PARABOLIC_VOLT_TARGET_ID = 2221030
PARABOLIC_VOLT_CURRENT_SOURCE_ID = 2241506
PARABOLIC_VOLT_CURRENT_TARGET_ID = 2221031
SPIRIT_OF_SNOW_SOURCE_ID = 400021067
SPIRIT_OF_SNOW_TARGET_ID = 2221014
SPIRIT_OF_SNOW_TICK_TARGET_ID = 2221015
FIELD_DURATION_MS = 4000
FIELD_START_MS = 960
HISTORICAL_SPIRIT_OF_SNOW = (
    Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-MS-Export")
    / "HistoricalSpiritOfSnow" / "kms370-400021067.zip"
)
HISTORICAL_SPIRIT_OF_SNOW_PREFIX = "Skill-40002.img-skill-400021067-"
SPIRIT_OF_SNOW_METADATA = migration.MS_EXPORT_ROOT / "400021067.xml"
RETIRED_ICE_AGE_VIDEO = ROOT / "clien/Data/Video/explorer-2221009.mcv"
RETIRED_STRING_IDS = {
    FREEZING_BREATH_TARGET_ID: "x221009",
    FALLING_TARGET_ID: "x221010",
    SPIRIT_OF_SNOW_TARGET_ID: "x221014",
    CHAIN_TARGET_ID: "x221017",
    MAIN_TARGET_ID: "x221020",
    FROZEN_LIGHTNING_TARGET_ID: "x221027",
    PARABOLIC_VOLT_TARGET_ID: "x221030",
}
REMOVED_STRING_IDS = {}
REMOVED_SKILL_IDS = (REMOVED_ICE_AGE_TICK_TARGET_ID,)
BASE_SKILL_IDS = (
    "2221000", "2221001", "2221002", "2221004", "2221003",
    "2221005", "2221006", "2221007", "2221008",
)
EARLY_CUSTOM_SKILL_IDS = tuple(str(skill_id) for skill_id in (
    FALLING_TARGET_ID, FALLING_FIRST_TARGET_ID, FALLING_SECOND_TARGET_ID,
    CHAIN_TARGET_ID, CHAIN_FIELD_TARGET_ID, CHAIN_FIELD_TICK_TARGET_ID,
    MAIN_TARGET_ID, PASSIVE_TARGET_ID,
))
PREVIOUS_CUSTOM_SKILL_IDS = tuple(str(skill_id) for skill_id in (
    FREEZING_BREATH_TARGET_ID,
    FALLING_TARGET_ID, FALLING_FIRST_TARGET_ID, FALLING_SECOND_TARGET_ID,
    REMOVED_ICE_AGE_TICK_TARGET_ID, 2221014, 2221015,
    CHAIN_TARGET_ID, CHAIN_FIELD_TARGET_ID, CHAIN_FIELD_TICK_TARGET_ID,
    MAIN_TARGET_ID, PASSIVE_TARGET_ID,
))
CURRENT_CUSTOM_SKILL_IDS = tuple(str(skill_id) for skill_id in (
    FREEZING_BREATH_TARGET_ID,
    FALLING_TARGET_ID, FALLING_FIRST_TARGET_ID, FALLING_SECOND_TARGET_ID,
    REMOVED_ICE_AGE_TICK_TARGET_ID,
    CHAIN_TARGET_ID, CHAIN_FIELD_TARGET_ID, CHAIN_FIELD_TICK_TARGET_ID,
    MAIN_TARGET_ID, PASSIVE_TARGET_ID,
    FROZEN_LIGHTNING_TARGET_ID, FROZEN_LIGHTNING_FIELD_TARGET_ID,
    FROZEN_LIGHTNING_ERUPTION_TARGET_ID,
    PARABOLIC_VOLT_TARGET_ID, PARABOLIC_VOLT_CURRENT_TARGET_ID,
))
RETIRED_ICE_AGE_CUSTOM_SKILL_IDS = tuple(str(skill_id) for skill_id in (
    FREEZING_BREATH_TARGET_ID,
    FALLING_TARGET_ID, FALLING_FIRST_TARGET_ID, FALLING_SECOND_TARGET_ID,
    REMOVED_ICE_AGE_TICK_TARGET_ID,
    SPIRIT_OF_SNOW_TARGET_ID, SPIRIT_OF_SNOW_TICK_TARGET_ID,
    CHAIN_TARGET_ID, CHAIN_FIELD_TARGET_ID, CHAIN_FIELD_TICK_TARGET_ID,
    MAIN_TARGET_ID, PASSIVE_TARGET_ID,
    FROZEN_LIGHTNING_TARGET_ID, FROZEN_LIGHTNING_FIELD_TARGET_ID,
    FROZEN_LIGHTNING_ERUPTION_TARGET_ID,
    PARABOLIC_VOLT_TARGET_ID, PARABOLIC_VOLT_CURRENT_TARGET_ID,
))
CUSTOM_SKILL_IDS = tuple(str(skill_id) for skill_id in (
    FREEZING_BREATH_TARGET_ID,
    FALLING_TARGET_ID, FALLING_FIRST_TARGET_ID, FALLING_SECOND_TARGET_ID,
    SPIRIT_OF_SNOW_TARGET_ID, SPIRIT_OF_SNOW_TICK_TARGET_ID,
    CHAIN_TARGET_ID, CHAIN_FIELD_TARGET_ID, CHAIN_FIELD_TICK_TARGET_ID,
    MAIN_TARGET_ID, PASSIVE_TARGET_ID,
    FROZEN_LIGHTNING_TARGET_ID, FROZEN_LIGHTNING_FIELD_TARGET_ID,
    FROZEN_LIGHTNING_ERUPTION_TARGET_ID,
    PARABOLIC_VOLT_TARGET_ID, PARABOLIC_VOLT_CURRENT_TARGET_ID,
))


def runtime_job() -> migration.RuntimeJob:
    migration.PARAMETER_SOURCE_IDS[FALLING_SOURCE_ID] = FALLING_FIRST_SOURCE_ID
    config = migration.JobConfig(
        "ilArchMage", 222, "224", "40002", (),
        frozenset({FALLING_SOURCE_ID, CHAIN_SOURCE_ID, MAIN_SOURCE_ID}),
        FALLING_TARGET_ID, "chainlightning", "i", True,
    )
    roots = migration.exported_roots()
    names = migration.source_names()
    freezing_breath = migration.engine.SkillSpec(
        target_id=FREEZING_BREATH_TARGET_ID,
        source_id=FREEZING_BREATH_SOURCE_ID,
        source_group="222",
        name="极冻吐息",
        damage=80,
        attack_count=4,
        mob_count=8,
        mp_con=22,
        cooldown=0,
        hidden=False,
        icon_source_id=FREEZING_BREATH_SOURCE_ID,
        effect_nodes=(),
        projectile_nodes=(),
        extra_nodes=(),
        lt=(-530, -190),
        rb=(20, 40),
        duration_seconds=13,
        include_hit=True,
    )
    falling = migration.make_spec(
        config, FALLING_SOURCE_ID, FALLING_TARGET_ID, True, roots, names
    )
    falling_first = migration.make_spec(
        config, FALLING_FIRST_SOURCE_ID, FALLING_FIRST_TARGET_ID, False, roots, names
    )
    falling_second = migration.make_spec(
        config, FALLING_SECOND_SOURCE_ID, FALLING_SECOND_TARGET_ID, False, roots, names
    )
    chain = migration.make_spec(
        config, CHAIN_SOURCE_ID, CHAIN_TARGET_ID, True, roots, names
    )
    chain_field = migration.make_spec(
        config, CHAIN_FIELD_SOURCE_ID, CHAIN_FIELD_TARGET_ID, False, roots, names
    )
    chain_tick = migration.make_spec(
        config, CHAIN_FIELD_SOURCE_ID, CHAIN_FIELD_TICK_TARGET_ID, False, roots, names
    )
    main = migration.make_spec(
        config, MAIN_SOURCE_ID, MAIN_TARGET_ID, True, roots, names
    )
    passive = migration.make_spec(
        config, PASSIVE_SOURCE_ID, PASSIVE_TARGET_ID, False, roots, names
    )
    frozen_lightning = migration.make_spec(
        config, FROZEN_LIGHTNING_SOURCE_ID, FROZEN_LIGHTNING_TARGET_ID, True, roots, names
    )
    frozen_lightning_field = migration.make_spec(
        config, FROZEN_LIGHTNING_FIELD_SOURCE_ID, FROZEN_LIGHTNING_FIELD_TARGET_ID,
        False, roots, names
    )
    frozen_lightning_eruption = migration.make_spec(
        config, FROZEN_LIGHTNING_ERUPTION_SOURCE_ID,
        FROZEN_LIGHTNING_ERUPTION_TARGET_ID, False, roots, names
    )
    parabolic_volt = migration.make_spec(
        config, PARABOLIC_VOLT_SOURCE_ID, PARABOLIC_VOLT_TARGET_ID, True, roots, names
    )
    parabolic_volt_current = migration.make_spec(
        config, PARABOLIC_VOLT_CURRENT_SOURCE_ID,
        PARABOLIC_VOLT_CURRENT_TARGET_ID, False, roots, names
    )
    spirit_of_snow = migration.make_spec(
        config, SPIRIT_OF_SNOW_SOURCE_ID, SPIRIT_OF_SNOW_TARGET_ID, True,
        roots, names
    )
    spirit_of_snow_tick = migration.make_spec(
        config, SPIRIT_OF_SNOW_SOURCE_ID, SPIRIT_OF_SNOW_TICK_TARGET_ID, False,
        roots, names
    )
    specs = (
        freezing_breath, spirit_of_snow, spirit_of_snow_tick,
        falling, falling_first, falling_second,
        chain, chain_field, chain_tick, main, passive,
        frozen_lightning, frozen_lightning_field, frozen_lightning_eruption,
        parabolic_volt, parabolic_volt_current,
    )
    if any(spec is None for spec in specs):
        raise RuntimeError("an Ice/Lightning source did not produce a skill spec")
    falling = replace(
        falling, name="落雷凝聚", hit_source_id=FALLING_FIRST_SOURCE_ID,
        include_hit=True, duration_seconds=None,
    )
    falling_first = replace(falling_first, name="落雷凝聚：奇数段", duration_seconds=None)
    falling_second = replace(falling_second, name="落雷凝聚：偶数段", duration_seconds=None)
    chain = replace(
        chain, name="闪电连击VI", lt=(-420, -250), rb=(420, 200)
    )
    chain_field = replace(
        chain_field, name="闪电连击VI：电流地带",
        duration_seconds=None, effect_nodes=(), extra_nodes=(),
    )
    chain_tick = replace(
        chain_tick, name="闪电连击VI：电流地带攻击",
        duration_seconds=None, effect_nodes=(), extra_nodes=(),
    )
    main = replace(main, name="暴风雪VI")
    passive = replace(passive, name="暴风雪VI：终极攻击", duration_seconds=None)
    frozen_lightning = replace(
        frozen_lightning, name="殛冻领域", duration_seconds=None,
        effect_nodes=(), extra_nodes=(), projectile_nodes=(),
    )
    frozen_lightning_field = replace(
        frozen_lightning_field, name="殛冻领域：领域攻击", duration_seconds=None,
        mp_con=0, cooldown=0, effect_nodes=(), extra_nodes=("special",),
        projectile_nodes=(),
    )
    frozen_lightning_eruption = replace(
        frozen_lightning_eruption, name="殛冻领域：魔力迸发", duration_seconds=None,
        mp_con=0, cooldown=0, effect_nodes=(), extra_nodes=(), projectile_nodes=(),
    )
    parabolic_volt = replace(
        parabolic_volt, name="圆弧雷鸣", duration_seconds=None,
        effect_nodes=("special",), extra_nodes=(), projectile_nodes=(),
    )
    parabolic_volt_current = replace(
        parabolic_volt_current, name="圆弧雷鸣：圆弧电流", duration_seconds=None,
        mp_con=0, cooldown=0, effect_nodes=(), extra_nodes=(), projectile_nodes=(),
    )
    spirit_of_snow = replace(
        spirit_of_snow, name="冰雪之精神", duration_seconds=None,
        effect_nodes=("effect",), extra_nodes=(), projectile_nodes=(),
        lt=(-900, -700), rb=(900, 250),
    )
    spirit_of_snow_tick = replace(
        spirit_of_snow_tick, name="冰雪之精神：召唤攻击", duration_seconds=None,
        mp_con=0, cooldown=0, effect_nodes=(), extra_nodes=(),
        projectile_nodes=(), lt=(-900, -700), rb=(900, 250),
    )
    typed_specs = (
        freezing_breath,
        falling, falling_first, falling_second,
        spirit_of_snow, spirit_of_snow_tick,
        chain, chain_field, chain_tick, main, passive,
        frozen_lightning, frozen_lightning_field, frozen_lightning_eruption,
        parabolic_volt, parabolic_volt_current,
    )
    return migration.RuntimeJob(
        config,
        typed_specs,
        {spec.target_id: spec.source_id for spec in typed_specs},
        {
            FREEZING_BREATH_SOURCE_ID: FREEZING_BREATH_TARGET_ID,
            SPIRIT_OF_SNOW_SOURCE_ID: SPIRIT_OF_SNOW_TARGET_ID,
            FALLING_SOURCE_ID: FALLING_TARGET_ID,
            FALLING_FIRST_SOURCE_ID: FALLING_FIRST_TARGET_ID,
            FALLING_SECOND_SOURCE_ID: FALLING_SECOND_TARGET_ID,
            CHAIN_SOURCE_ID: CHAIN_TARGET_ID,
            CHAIN_FIELD_SOURCE_ID: CHAIN_FIELD_TARGET_ID,
            MAIN_SOURCE_ID: MAIN_TARGET_ID,
            PASSIVE_SOURCE_ID: PASSIVE_TARGET_ID,
            FROZEN_LIGHTNING_SOURCE_ID: FROZEN_LIGHTNING_TARGET_ID,
            FROZEN_LIGHTNING_FIELD_SOURCE_ID: FROZEN_LIGHTNING_FIELD_TARGET_ID,
            FROZEN_LIGHTNING_ERUPTION_SOURCE_ID: FROZEN_LIGHTNING_ERUPTION_TARGET_ID,
            PARABOLIC_VOLT_SOURCE_ID: PARABOLIC_VOLT_TARGET_ID,
            PARABOLIC_VOLT_CURRENT_SOURCE_ID: PARABOLIC_VOLT_CURRENT_TARGET_ID,
        },
    )


def legacy_action(spec) -> str:
    if spec.target_id == FREEZING_BREATH_TARGET_ID:
        return "chainlightning"
    return "blizzard" if spec.target_id in (
        MAIN_TARGET_ID, PASSIVE_TARGET_ID,
        SPIRIT_OF_SNOW_TARGET_ID, SPIRIT_OF_SNOW_TICK_TARGET_ID,
        FROZEN_LIGHTNING_TARGET_ID, FROZEN_LIGHTNING_FIELD_TARGET_ID,
        FROZEN_LIGHTNING_ERUPTION_TARGET_ID,
    ) else "chainlightning"


def set_hit_variant_metadata(variant, random_origin: int, layered: bool = False) -> None:
    migration.engine.set_int(variant, "randomHitOrigin", random_origin)
    if layered:
        migration.engine.set_int(variant, "onlyOnce", 1)
        migration.engine.set_int(variant, "useZ", 1)
        migration.engine.set_int(variant, "z", 1)


def historical_canvas(
        archive: zipfile.ZipFile,
        member: str,
        name: str,
        parent: WzSubProperty,
        key: WzKey,
        delay: int,
        origin: str,
) -> WzCanvasProperty:
    try:
        payload = archive.read(member)
    except KeyError as error:
        raise RuntimeError(f"missing historical skill frame: {member}") from error
    with Image.open(io.BytesIO(payload)) as opened:
        image = opened.convert("RGBA")
    frame = WzCanvasProperty(name, parent)
    frame.width, frame.height = image.size
    frame.format = migration.engine.base.CANVAS_FORMAT
    frame.format2 = 0
    frame._png_data = migration.engine.base.encode_canvas_payload(
        image, frame.format, frame.width, frame.height,
        key=key, listwz=False, zlib_level=9,
    )
    frame._png_length = len(frame._png_data)
    if origin == "bottom":
        migration.engine.set_vector(frame, "origin", (frame.width // 2, frame.height))
    elif origin == "icon":
        migration.engine.set_vector(frame, "origin", (0, frame.height))
    else:
        migration.engine.set_vector(frame, "origin", (frame.width // 2, frame.height // 2))
    migration.engine.set_int(frame, "delay", delay)
    return frame


def rebuild_freezing_breath_assets(node, key, groups, metadata) -> None:
    source = migration.source_node(groups, FREEZING_BREATH_SOURCE_ID)
    for icon_name in ("icon", "iconMouseOver", "iconDisabled"):
        icon = source.get(icon_name)
        if not isinstance(icon, WzCanvasProperty):
            raise RuntimeError(f"missing Freezing Breath icon: {icon_name}")
        node.add(migration.engine.base.make_icon(icon, icon_name, node, key))

    prepare = migration.engine.tracks(
        groups, metadata, FREEZING_BREATH_SOURCE_ID, "prepare"
    )
    keydown = migration.engine.tracks(
        groups, metadata, FREEZING_BREATH_SOURCE_ID, "keydown"
    )
    keydown0 = migration.engine.tracks(
        groups, metadata, FREEZING_BREATH_SOURCE_ID, "keydown0"
    )
    keydownend = migration.engine.tracks(
        groups, metadata, FREEZING_BREATH_SOURCE_ID, "keydownend"
    )
    if not prepare or not keydown or not keydown0 or not keydownend:
        raise RuntimeError("Freezing Breath cast tracks are incomplete")
    if tuple(map(len, (prepare[0], keydown[0], keydown0[0], keydownend[0]))) != (4, 10, 8, 5):
        raise RuntimeError("unexpected Freezing Breath cast frame counts")

    effect = WzSubProperty("effect", node)
    migration.engine.base.merge_tracks(prepare[0], [], effect, key)
    migration.engine.base.merge_tracks(
        keydown[0], keydown0[0], effect, key, start_index=4
    )
    migration.engine.base.merge_tracks(
        keydownend[0], [], effect, key, start_index=14
    )
    node.add(effect)

    variants = migration.engine.tracks(
        groups, metadata, FREEZING_BREATH_SOURCE_ID, "special"
    )
    if len(variants) != 3 or any(len(variant) != 8 for variant in variants):
        raise RuntimeError("unexpected Freezing Breath monster-hit frame counts")
    hit = WzSubProperty("hit", node)
    for variant_index, source_frames in enumerate(variants):
        variant = WzSubProperty(str(variant_index), hit)
        migration.engine.base.merge_tracks(source_frames, [], variant, key)
        set_hit_variant_metadata(variant, 25, layered=True)
        migration.engine.set_int(variant, "pos", 1)
        hit.add(variant)
    migration.engine.set_int(hit, "randomHit", 1)
    node.add(hit)


def spirit_metadata_node(root, path: str):
    node = root
    for segment in path.split("/"):
        node = migration.named_child(node, segment)
        if node is None:
            raise RuntimeError(f"missing Spirit of Snow metadata: {path}")
    return node


def spirit_origin(frame) -> tuple[int, int]:
    origin = migration.named_child(frame, "origin")
    if origin is None:
        raise RuntimeError("Spirit of Snow frame has no origin")
    return int(origin.get("x")), int(origin.get("y"))


def spirit_canvas(archive, suffix, name, parent, key, metadata) -> WzCanvasProperty:
    frame = historical_canvas(
        archive, HISTORICAL_SPIRIT_OF_SNOW_PREFIX + suffix + ".png",
        name, parent, key, migration.scalar(metadata, "delay", 90), "center",
    )
    migration.engine.set_vector(frame, "origin", spirit_origin(metadata))
    return frame


def rebuild_spirit_assets(node, key, tick: bool) -> None:
    if not HISTORICAL_SPIRIT_OF_SNOW.is_file():
        raise RuntimeError(
            f"missing historical Spirit of Snow archive: {HISTORICAL_SPIRIT_OF_SNOW}"
        )
    metadata_root = migration.ET.parse(SPIRIT_OF_SNOW_METADATA).getroot()
    with zipfile.ZipFile(HISTORICAL_SPIRIT_OF_SNOW) as archive:
        if not tick:
            for icon_name in ("icon", "iconMouseOver", "iconDisabled"):
                source = spirit_metadata_node(metadata_root, icon_name)
                node.add(spirit_canvas(
                    archive, icon_name, icon_name, node, key, source
                ))
            effect_source = spirit_metadata_node(metadata_root, "effect")
            effect = WzSubProperty("effect", node)
            for source in effect_source:
                if source.tag != "canvas" or not source.get("name", "").isdigit():
                    continue
                effect.add(spirit_canvas(
                    archive, f"effect-{source.get('name')}",
                    source.get("name"), effect, key, source,
                ))
            node.add(effect)

        source_name = "hit2" if tick else "hit"
        hit_source = spirit_metadata_node(metadata_root, source_name)
        hit = WzSubProperty("hit", node)
        for source_variant in hit_source:
            if source_variant.tag != "imgdir" or not source_variant.get("name", "").isdigit():
                continue
            variant = WzSubProperty(source_variant.get("name"), hit)
            for source in source_variant:
                if source.tag != "canvas" or not source.get("name", "").isdigit():
                    continue
                suffix = f"{source_name}-{source_variant.get('name')}-{source.get('name')}"
                variant.add(spirit_canvas(
                    archive, suffix, source.get("name"), variant, key, source,
                ))
            set_hit_variant_metadata(variant, 35 if tick else 30, layered=True)
            migration.engine.set_int(variant, "delayShowDamage", 720)
            migration.engine.set_int(variant, "pos", 1)
            hit.add(variant)
        migration.engine.set_int(hit, "randomHit", 1)
        node.add(hit)


def build_replacement_node(spec, parent, key, groups, metadata) -> WzSubProperty:
    node = WzSubProperty(str(spec.target_id), parent)
    action = WzSubProperty("action", node)
    migration.engine.set_string(action, "0", legacy_action(spec))
    node.add(action)
    node.add(migration.engine.make_levels(spec, node))
    migration.engine.set_int(node, "masterLevel", migration.MASTER_LEVEL)
    migration.engine.set_string(node, "elemAttr", "i")
    if spec.hidden:
        migration.engine.set_int(node, "invisible", 1)
    if spec.target_id == FREEZING_BREATH_TARGET_ID:
        rebuild_freezing_breath_assets(node, key, groups, metadata)
    elif spec.target_id in (SPIRIT_OF_SNOW_TARGET_ID, SPIRIT_OF_SNOW_TICK_TARGET_ID):
        rebuild_spirit_assets(node, key, spec.hidden)
    else:
        raise RuntimeError(f"not a replacement skill: {spec.target_id}")
    return node


def rebuild_spirit_tick_hit(node, key, groups, metadata) -> None:
    variants = migration.engine.tracks(
        groups, metadata, SPIRIT_OF_SNOW_SOURCE_ID, "hit2"
    )
    if len(variants) != 3 or any(len(variant) != 13 for variant in variants):
        raise RuntimeError("unexpected Spirit of Snow hit2 frame count")
    hit = WzSubProperty("hit", node)
    for variant_index, source_frames in enumerate(variants):
        variant = WzSubProperty(str(variant_index), hit)
        migration.engine.base.merge_tracks(source_frames, [], variant, key)
        set_hit_variant_metadata(variant, 35, layered=True)
        migration.engine.set_int(variant, "delayShowDamage", 720)
        migration.engine.set_int(variant, "pos", 1)
        hit.add(variant)
    migration.engine.set_int(hit, "randomHit", 1)
    node._children.pop("hit", None)
    node.add(hit)


def set_fixed_levels(node, spec) -> None:
    for level in node.get("level").children():
        migration.engine.set_int(level, "damage", spec.damage)
        migration.engine.set_int(level, "mad", spec.damage)
        migration.engine.set_int(level, "attackCount", spec.attack_count)
        migration.engine.set_int(level, "mobCount", spec.mob_count)
        migration.engine.set_int(level, "mpCon", spec.mp_con)
        migration.engine.set_int(level, "cooltime", spec.cooldown)
        migration.engine.set_vector(level, "lt", spec.lt)
        migration.engine.set_vector(level, "rb", spec.rb)
        if spec.duration_seconds is None:
            level._children.pop("time", None)
        else:
            migration.engine.set_int(level, "time", spec.duration_seconds)


def rebuild_frozen_lightning_field_hit(node, key, groups, metadata) -> None:
    special_variants = migration.engine.tracks(
        groups, metadata, FROZEN_LIGHTNING_FIELD_SOURCE_ID, "special"
    )
    hit_variants = migration.engine.tracks(
        groups, metadata, FROZEN_LIGHTNING_FIELD_SOURCE_ID, "hit"
    )
    if (len(special_variants) != 3 or len(hit_variants) != 3
            or any(len(variant) != 12 for variant in special_variants)
            or any(len(variant) != 10 for variant in hit_variants)):
        raise RuntimeError("unexpected Frozen Lightning field frame count")

    hit = WzSubProperty("hit", node)
    for variant_index, (special_track, hit_track) in enumerate(
            zip(special_variants, hit_variants)):
        variant = WzSubProperty(str(variant_index), hit)
        elapsed = 0
        for frame_index, special_frame in enumerate(special_track):
            hit_frame = active_track_frame(hit_track, elapsed)
            if hit_frame is None:
                canvas, frame_meta = special_frame
                frame = migration.engine.base.encode_target_canvas(
                    canvas, str(frame_index), variant, key, meta=frame_meta
                )
            else:
                frame = migration.engine.base.compose_frames(
                    special_frame, hit_frame, str(frame_index), variant, key
                )
            migration.engine.set_int(
                frame, "delay", migration.engine.base.frame_delay(*special_frame)
            )
            variant.add(frame)
            elapsed += migration.engine.base.frame_delay(*special_frame)
        set_hit_variant_metadata(variant, (40, 70, 100)[variant_index], layered=True)
        hit.add(variant)
    migration.engine.set_int(hit, "randomHit", 1)
    node._children.pop("special", None)
    node._children.pop("hit", None)
    node.add(hit)


def flatten_chain_mob(node) -> None:
    source = node.get("mob/0")
    frames = migration.engine.base.numeric_canvases(source)
    if not frames:
        raise RuntimeError("missing Chain Lightning VI mob animation")
    target = WzSubProperty("mob", node)
    for frame in frames:
        target.add(migration.engine.base.clone_property(frame, frame.name, target))
    migration.engine.set_int(target, "pos", 2)
    migration.engine.set_int(target, "repeat", 1)
    node._children.pop("mob", None)
    node.add(target)


def rebuild_chain_effect(node, key, groups, metadata) -> None:
    primary_variants = migration.engine.tracks(
        groups, metadata, CHAIN_SOURCE_ID, "effect"
    )
    secondary_variants = migration.engine.tracks(
        groups, metadata, CHAIN_SOURCE_ID, "effect0"
    )
    if not primary_variants or not secondary_variants:
        raise RuntimeError("missing Chain Lightning VI effect layers")
    primary = primary_variants[0]
    secondary = secondary_variants[0]
    effect = WzSubProperty("effect", node)
    elapsed = 0
    secondary_index = 0
    secondary_end = migration.engine.base.frame_delay(*secondary[0])
    for index, first in enumerate(primary):
        while elapsed >= secondary_end and secondary_index + 1 < len(secondary):
            secondary_index += 1
            secondary_end += migration.engine.base.frame_delay(*secondary[secondary_index])
        frame = migration.engine.base.compose_frames(
            secondary[secondary_index], first, str(index), effect, key
        )
        delay = migration.engine.base.frame_delay(*first)
        migration.engine.set_int(frame, "delay", delay)
        effect.add(frame)
        elapsed += delay
    node._children.pop("effect", None)
    node.add(effect)


def rebuild_blizzard_effect(node, key, groups, metadata) -> None:
    primary_variants = migration.engine.tracks(
        groups, metadata, MAIN_SOURCE_ID, "effect"
    )
    secondary_variants = migration.engine.tracks(
        groups, metadata, MAIN_SOURCE_ID, "effect0"
    )
    if not primary_variants or not secondary_variants:
        raise RuntimeError("missing Blizzard VI effect layers")
    primary = primary_variants[0]
    secondary = secondary_variants[0]
    if len(primary) != len(secondary):
        raise RuntimeError("unexpected Blizzard VI effect layer lengths")
    effect = WzSubProperty("effect", node)
    for index, (first, second) in enumerate(zip(primary, secondary)):
        frame = migration.engine.base.compose_frames(second, first, str(index), effect, key)
        migration.engine.set_int(
            frame, "delay", migration.engine.base.frame_delay(*first)
        )
        effect.add(frame)
    node._children.pop("effect", None)
    node.add(effect)


def active_track_frame(track, elapsed: int):
    end = 0
    for frame in track:
        end += migration.engine.base.frame_delay(*frame)
        if elapsed < end:
            return frame
    return None


def rebuild_falling_effect(node, key, groups, metadata) -> None:
    cast_variants = migration.engine.tracks(
        groups, metadata, FALLING_SOURCE_ID, "effect"
    )
    first_variants = migration.engine.tracks(
        groups, metadata, FALLING_FIRST_SOURCE_ID, "effect"
    )
    second_variants = migration.engine.tracks(
        groups, metadata, FALLING_SECOND_SOURCE_ID, "effect"
    )
    if not cast_variants or not first_variants or not second_variants:
        raise RuntimeError("missing Falling Thunder cast or lightning-column layers")
    cast_track = cast_variants[0]
    stage_tracks = (first_variants[0], second_variants[0])
    if len(cast_track) != 16 or any(len(track) != 15 for track in stage_tracks):
        raise RuntimeError("unexpected Falling Thunder cast or lightning-column frame count")

    effect = WzSubProperty("effect", node)
    sample_indices = (2, 5, 8, 11, 14)
    elapsed = 0
    for output_index in range(40):
        stage_index, sample_index = divmod(output_index, len(sample_indices))
        column_frame = stage_tracks[stage_index % len(stage_tracks)][
            sample_indices[sample_index]
        ]
        cast_frame = active_track_frame(cast_track, elapsed)
        if cast_frame is None:
            canvas, frame_meta = column_frame
            frame = migration.engine.base.encode_target_canvas(
                canvas, str(output_index), effect, key, meta=frame_meta
            )
        else:
            frame = migration.engine.base.compose_frames(
                cast_frame, column_frame, str(output_index), effect, key
            )
        migration.engine.set_int(frame, "delay", 60)
        effect.add(frame)
        elapsed += 60
    node._children.pop("effect", None)
    node.add(effect)


def rebuild_chain_hit_with_field(node, key, groups, metadata) -> None:
    main_variants = migration.engine.tracks(
        groups, metadata, CHAIN_SOURCE_ID, "hit"
    )
    tile_variants = migration.engine.tracks(
        groups, metadata, CHAIN_FIELD_SOURCE_ID, "tile"
    )
    finish_variants = migration.engine.tracks(
        groups, metadata, CHAIN_FIELD_SOURCE_ID, "finish"
    )
    if not main_variants or not tile_variants or not finish_variants:
        raise RuntimeError("missing Chain Lightning VI hit or field layers")
    main_track = main_variants[0]
    tile_track = tile_variants[0]
    finish_track = finish_variants[0]
    if len(main_track) != 8 or len(tile_track) != 24 or len(finish_track) != 8:
        raise RuntimeError("unexpected Chain Lightning VI hit or field frame count")

    hit = WzSubProperty("hit", node)
    variant = WzSubProperty("0", hit)
    output_index = 0
    main_elapsed = 0
    for source in main_track:
        canvas, frame_meta = source
        frame = migration.engine.base.encode_target_canvas(
            canvas, str(output_index), variant, key, meta=frame_meta
        )
        variant.add(frame)
        main_elapsed += migration.engine.base.frame_delay(*source)
        output_index += 1
    if main_elapsed >= FIELD_START_MS:
        raise RuntimeError(f"Chain Lightning VI main hit is too long: {main_elapsed}ms")

    canvas, frame_meta = main_track[-1]
    prelude = migration.engine.base.encode_target_canvas(
        canvas, str(output_index), variant, key, meta=frame_meta
    )
    migration.engine.set_int(prelude, "a0", 0)
    migration.engine.set_int(prelude, "a1", 0)
    migration.engine.set_int(prelude, "delay", FIELD_START_MS - main_elapsed)
    variant.add(prelude)
    output_index += 1

    field_elapsed = 0
    for source in tile_track:
        canvas, frame_meta = source
        frame = migration.engine.base.encode_target_canvas(
            canvas, str(output_index), variant, key, meta=frame_meta
        )
        variant.add(frame)
        field_elapsed += migration.engine.base.frame_delay(*source)
        output_index += 1
    cycle_index = 8
    while field_elapsed < FIELD_DURATION_MS:
        source = tile_track[cycle_index]
        canvas, frame_meta = source
        frame = migration.engine.base.encode_target_canvas(
            canvas, str(output_index), variant, key, meta=frame_meta
        )
        variant.add(frame)
        field_elapsed += migration.engine.base.frame_delay(*source)
        output_index += 1
        cycle_index += 1
        if cycle_index >= len(tile_track):
            cycle_index = 8
    for source in finish_track:
        canvas, frame_meta = source
        frame = migration.engine.base.encode_target_canvas(
            canvas, str(output_index), variant, key, meta=frame_meta
        )
        variant.add(frame)
        output_index += 1
    set_hit_variant_metadata(variant, 35, layered=True)
    hit.add(variant)
    node._children.pop("hit", None)
    node.add(hit)


def add_legacy_metadata(node, spec, key, groups, metadata) -> None:
    migration.engine.set_string(node.get("action"), "0", legacy_action(spec))
    prop = {
        CHAIN_TARGET_ID: 100,
        MAIN_TARGET_ID: 70,
        PASSIVE_TARGET_ID: 70,
    }.get(spec.target_id)
    if prop is not None:
        for level in node.get("level").children():
            migration.engine.set_int(level, "prop", prop)

    hit = node.get("hit")
    if not isinstance(hit, WzSubProperty):
        raise RuntimeError(f"missing hit node: {spec.target_id}")
    if spec.target_id == FREEZING_BREATH_TARGET_ID:
        set_fixed_levels(node, spec)
        node._children.pop("effect", None)
        node._children.pop("hit", None)
        for icon_name in ("icon", "iconMouseOver", "iconDisabled"):
            node._children.pop(icon_name, None)
        rebuild_freezing_breath_assets(node, key, groups, metadata)
        return
    if spec.target_id == SPIRIT_OF_SNOW_TARGET_ID:
        set_fixed_levels(node, spec)
        migration.engine.set_int(hit, "randomHit", 1)
        for variant_index in range(3):
            variant = hit.get(str(variant_index))
            if not isinstance(variant, WzSubProperty):
                raise RuntimeError("missing Spirit of Snow hit variant")
            set_hit_variant_metadata(variant, 30, layered=True)
            migration.engine.set_int(variant, "delayShowDamage", 720)
            migration.engine.set_int(variant, "pos", 1)
        return
    if spec.target_id == SPIRIT_OF_SNOW_TICK_TARGET_ID:
        set_fixed_levels(node, spec)
        rebuild_spirit_tick_hit(node, key, groups, metadata)
        return
    if spec.target_id == FALLING_TARGET_ID:
        rebuild_falling_effect(node, key, groups, metadata)
        set_hit_variant_metadata(hit.get("0"), 25)
        return
    if spec.target_id in (FALLING_FIRST_TARGET_ID, FALLING_SECOND_TARGET_ID):
        node._children.pop("effect", None)
        set_hit_variant_metadata(hit.get("0"), 25)
        return
    if spec.target_id == CHAIN_TARGET_ID:
        rebuild_chain_effect(node, key, groups, metadata)
        rebuild_chain_hit_with_field(node, key, groups, metadata)
        flatten_chain_mob(node)
        for level in node.get("level").children():
            migration.engine.set_vector(level, "lt", spec.lt)
            migration.engine.set_vector(level, "rb", spec.rb)
        return
    if spec.target_id in (CHAIN_FIELD_TARGET_ID, CHAIN_FIELD_TICK_TARGET_ID):
        migration.engine.set_int(hit, "randomHit", 1)
        for variant_index in range(3):
            set_hit_variant_metadata(hit.get(str(variant_index)), 25, layered=True)
        return
    if spec.target_id == MAIN_TARGET_ID:
        rebuild_blizzard_effect(node, key, groups, metadata)
        variant = hit.get("0")
        if not isinstance(variant, WzSubProperty):
            raise RuntimeError("missing Blizzard VI hit variant")
        # The old client supports this placement field. The modern random delay
        # fields are intentionally omitted because they are not legacy-safe.
        migration.engine.set_int(variant, "randomHitOrigin", 40)
        return
    if spec.target_id == FROZEN_LIGHTNING_TARGET_ID:
        set_hit_variant_metadata(hit.get("0"), 80, layered=True)
        return
    if spec.target_id == FROZEN_LIGHTNING_FIELD_TARGET_ID:
        rebuild_frozen_lightning_field_hit(node, key, groups, metadata)
        return
    if spec.target_id == FROZEN_LIGHTNING_ERUPTION_TARGET_ID:
        set_hit_variant_metadata(hit.get("0"), 80, layered=True)
        return
    if spec.target_id == PARABOLIC_VOLT_TARGET_ID:
        set_hit_variant_metadata(hit.get("0"), 50, layered=True)
        return
    if spec.target_id == PARABOLIC_VOLT_CURRENT_TARGET_ID:
        migration.engine.set_int(hit, "randomHit", 1)
        set_hit_variant_metadata(hit.get("0"), 30, layered=True)
        return

    metadata_root = migration.ET.parse(
        migration.MS_EXPORT_ROOT / f"{PASSIVE_SOURCE_ID}.xml"
    ).getroot()
    metadata_hit = migration.named_child(metadata_root, "hit")
    if metadata_hit is None:
        raise RuntimeError("missing final-attack hit metadata")
    migration.engine.set_int(hit, "randomHit", 1)
    variants = [child for child in metadata_hit if child.get("name", "").isdigit()]
    for source_variant in variants:
        target_variant = hit.get(source_variant.get("name"))
        if not isinstance(target_variant, WzSubProperty):
            raise RuntimeError(f"missing final-attack variant: {source_variant.get('name')}")
        migration.engine.set_int(
            target_variant,
            "delayShowDamage",
            migration.scalar(source_variant, "delayShowDamage"),
        )
        migration.engine.set_int(target_variant, "pos", migration.scalar(source_variant, "pos"))


def configure_duration_overrides() -> None:
    migration.DURATION_OVERRIDES[SPIRIT_OF_SNOW_SOURCE_ID] = None
    migration.DURATION_OVERRIDES[FALLING_SOURCE_ID] = None
    migration.DURATION_OVERRIDES[FALLING_FIRST_SOURCE_ID] = None
    migration.DURATION_OVERRIDES[FALLING_SECOND_SOURCE_ID] = None
    migration.DURATION_OVERRIDES.pop(CHAIN_SOURCE_ID, None)
    migration.DURATION_OVERRIDES[CHAIN_FIELD_SOURCE_ID] = None
    migration.DURATION_OVERRIDES.pop(MAIN_SOURCE_ID, None)
    migration.DURATION_OVERRIDES[PASSIVE_SOURCE_ID] = None
    migration.DURATION_OVERRIDES[FROZEN_LIGHTNING_SOURCE_ID] = None
    migration.DURATION_OVERRIDES[FROZEN_LIGHTNING_FIELD_SOURCE_ID] = None
    migration.DURATION_OVERRIDES[FROZEN_LIGHTNING_ERUPTION_SOURCE_ID] = None
    migration.DURATION_OVERRIDES[PARABOLIC_VOLT_SOURCE_ID] = None
    migration.DURATION_OVERRIDES[PARABOLIC_VOLT_CURRENT_SOURCE_ID] = None


def build_client_record(job: migration.RuntimeJob):
    configure_duration_overrides()
    migration.configure(job)
    groups, _, metadata = migration.engine.load_sources()
    source_string_path = migration.TMS_ROOT / "String" / "Skill.img"
    strings = WzImage.from_bytes(
        source_string_path.read_bytes(),
        key=WzKey.for_region("BMS"),
        name=source_string_path.name,
    ).parse()
    client_bytes = migration.engine.CLIENT_SKILL.read_bytes()
    image = WzImage.from_bytes(
        client_bytes,
        key=WzKey.for_region("GMS"),
        name=migration.engine.CLIENT_SKILL.name,
    )
    root = image.parse()
    skill_root = root.get("skill")
    if not isinstance(skill_root, WzSubProperty):
        raise RuntimeError("client 222.img has no skill root")
    _, _, _, names, records, _ = locate_skill_tail(migration.engine.CLIENT_SKILL)
    raw_records = {
        int(name): client_bytes[start:end]
        for name, (start, end) in zip(names, records)
        if name.isdigit()
    }
    specs = {spec.target_id: spec for spec in job.skills}
    replacements = {
        FREEZING_BREATH_TARGET_ID,
        SPIRIT_OF_SNOW_TARGET_ID, SPIRIT_OF_SNOW_TICK_TARGET_ID,
    }
    encoded_records = []
    for skill_id_text in CUSTOM_SKILL_IDS:
        skill_id = int(skill_id_text)
        if skill_id not in replacements:
            if skill_id not in raw_records:
                raise RuntimeError(f"missing unchanged client skill record: {skill_id}")
            encoded_records.append(raw_records[skill_id])
            continue
        node = build_replacement_node(
            specs[skill_id], skill_root, image.wz_file.reader.key, groups, metadata
        )
        encoded = _encode_property_list((node,), image.wz_file.reader)
        count = encode_compressed_int(1)
        if not encoded.startswith(count):
            raise RuntimeError("unexpected encoded replacement property prefix")
        encoded_records.append(encoded[len(count):])
    return b"".join(encoded_records), strings


def locate_skill_tail(path: Path):
    image, reader = retire.standalone_reader(path)
    retire.enter_root_property_list(reader)
    root_count = reader.read_compressed_int()
    if root_count != 2:
        raise RuntimeError(f"unexpected client 222 root count: {root_count}")
    for root_index in range(root_count):
        name = reader.read_string_block(0)
        tag = reader.read_byte()
        if tag != 9:
            raise RuntimeError(f"unexpected root property tag: {name}/{tag}")
        block_size = reader.read_u32()
        block_end = reader.position + block_size
        if name != "skill":
            reader.seek(block_end)
            continue
        if root_index != root_count - 1 or block_end != path.stat().st_size:
            raise RuntimeError("client 222 skill block must remain the final root property")
        if reader.read_string_block(0) != "Property":
            raise RuntimeError("client 222 skill root is not a Property")
        reader.skip(2)
        count_offset = reader.position
        count = reader.read_compressed_int()
        names = []
        records = []
        for _ in range(count):
            start = reader.position
            child_name = reader.read_string_block(0)
            child_tag = reader.read_byte()
            if child_tag != 9:
                raise RuntimeError(f"unexpected skill child tag: {child_name}/{child_tag}")
            child_size = reader.read_u32()
            reader.seek(reader.position + child_size)
            names.append(child_name)
            records.append((start, reader.position))
        return image, count_offset, count, tuple(names), tuple(records), block_end
    raise RuntimeError("client 222.img has no skill block")


def patch_client_skill(record: bytes) -> tuple[int, int]:
    path = migration.engine.CLIENT_SKILL
    _, count_offset, count, names, records, block_end = locate_skill_tail(path)
    if names == BASE_SKILL_IDS:
        record_offset = records[-1][1]
    elif names == BASE_SKILL_IDS + (str(MAIN_TARGET_ID),):
        record_offset = records[-1][0]
    elif names == BASE_SKILL_IDS + (str(MAIN_TARGET_ID), str(PASSIVE_TARGET_ID)):
        record_offset = records[-2][0]
    elif names in (
            BASE_SKILL_IDS + EARLY_CUSTOM_SKILL_IDS,
            BASE_SKILL_IDS + PREVIOUS_CUSTOM_SKILL_IDS,
            BASE_SKILL_IDS + CURRENT_CUSTOM_SKILL_IDS,
            BASE_SKILL_IDS + RETIRED_ICE_AGE_CUSTOM_SKILL_IDS,
            BASE_SKILL_IDS + CUSTOM_SKILL_IDS,
    ):
        record_offset = records[len(BASE_SKILL_IDS)][0]
    else:
        raise RuntimeError(f"unexpected visible client 222 skills: {names}")
    if record_offset + len(record) > block_end:
        raise RuntimeError("Ice/Lightning records do not fit retired client payload")
    with path.open("r+b") as stream:
        stream.seek(record_offset)
        stream.write(record)
        if count != len(BASE_SKILL_IDS) + len(CUSTOM_SKILL_IDS):
            stream.seek(count_offset)
            stream.write(encode_compressed_int(len(BASE_SKILL_IDS) + len(CUSTOM_SKILL_IDS)))
        stream.flush()
        os.fsync(stream.fileno())
    return count, len(BASE_SKILL_IDS) + len(CUSTOM_SKILL_IDS)


def synchronize_client_strings() -> int:
    path = migration.CLIENT_STRING
    reader, locations = retire.top_level_name_locations(path)
    patches = []
    for target_id, retired_id in RETIRED_STRING_IDS.items():
        if str(target_id) in locations:
            continue
        if retired_id not in locations:
            raise RuntimeError(f"missing retired client string node: {retired_id}")
        offset, length, encoding, indirected = locations[retired_id]
        if indirected:
            raise RuntimeError("refusing to patch an indirect client string name")
        encoded = re_encrypt_string(reader, str(target_id), encoding)
        if len(encoded) != length:
            raise RuntimeError("client string reactivation changed byte length")
        patches.append((offset, encoded))
        locations[str(target_id)] = locations.pop(retired_id)
    for target_id, retired_id in REMOVED_STRING_IDS.items():
        live_id = str(target_id)
        if retired_id in locations:
            continue
        if live_id not in locations:
            raise RuntimeError(f"missing live client string node to retire: {live_id}")
        offset, length, encoding, indirected = locations[live_id]
        if indirected:
            raise RuntimeError("refusing to patch an indirect client string name")
        encoded = re_encrypt_string(reader, retired_id, encoding)
        if len(encoded) != length:
            raise RuntimeError("client string retirement changed byte length")
        patches.append((offset, encoded))
    retire.patch_many(path, patches)
    return len(patches)


def patch_client_string_values() -> int:
    image = WzImage.from_bytes(
        migration.CLIENT_STRING.read_bytes(),
        key=WzKey.for_region("GMS"),
        name=migration.CLIENT_STRING.name,
    )
    root = image.parse()
    replacements = {
        str(FREEZING_BREATH_TARGET_ID): {
            "name": "极冻吐息",
            "desc": "释放极寒吐息冻结前方敌人。",
            "level": "消耗MP 22，最多攻击8名敌人，以80%伤害攻击4次，冻结13秒，无冷却时间",
        },
        str(SPIRIT_OF_SNOW_TARGET_ID): {
            "name": "冰雪之灵",
            "desc": "召唤冰雪之精神，在固定范围内周期攻击敌人。",
            "level": "消耗MP 1000，最多攻击10名敌人，以1715%伤害攻击12次，冷却时间120秒",
        },
    }
    patches = []
    for skill_id, values in replacements.items():
        node = root.get(skill_id)
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"missing active client string node: {skill_id}")
        for child in node.children():
            replacement = None
            if child.name in ("name", "desc"):
                replacement = values[child.name]
            elif child.name.startswith("h") and child.name[1:].isdigit():
                replacement = values["level"]
            if replacement is None:
                continue
            old_value = str(child.value)
            if len(replacement) > len(old_value):
                raise RuntimeError(
                    f"client string replacement is too long: {skill_id}/{child.name}"
                )
            replacement = replacement.ljust(len(old_value))
            encoded = re_encrypt_string(
                image.wz_file.reader, replacement, child._encoding
            )
            if child._indirected or len(encoded) != child._payload_length:
                raise RuntimeError(
                    f"client string replacement changed layout: {skill_id}/{child.name}"
                )
            if replacement != old_value:
                patches.append((child._payload_offset, encoded))
    retire.patch_many(migration.CLIENT_STRING, patches)
    return len(patches)


def reactivate_effect_marker() -> bool:
    path = migration.engine.CLIENT_MAP_EFFECT
    _, reader = retire.standalone_reader(path)
    retire.enter_root_property_list(reader)
    retire.enter_subproperty(reader, 0, "customSkill")
    child_list_offset = reader.position
    try:
        offset, length, encoding, indirected, _ = retire.read_named_extended_child(
            reader, 0, "retiredIL_"
        )
    except KeyError:
        reader.seek(child_list_offset)
        retire.read_named_extended_child(reader, 0, "ilArchMage")
        return False
    if indirected:
        raise RuntimeError("refusing to patch shared retiredIL_ marker name")
    encoded = re_encrypt_string(reader, "ilArchMage", encoding)
    if len(encoded) != length:
        raise RuntimeError("Map Effect marker reactivation changed byte length")
    retire.patch_bytes(path, offset, encoded)
    return True


def replace_xml_blocks(
        path: Path, parent_name: str | None, target_ids, blocks) -> None:
    text = path.read_text(encoding="utf-8")
    for target_id in target_ids:
        text = migration.engine.remove_xml_block(text, str(target_id))
    if parent_name is None:
        closing = text.rfind("</imgdir>")
    else:
        start, end = migration.engine.find_imgdir_block(text, parent_name)
        closing = text.rfind("</imgdir>", start, end)
    if closing < 0:
        raise RuntimeError(f"missing insertion point: {path}")
    updated = text[:closing].rstrip() + "\n" + "\n".join(blocks) + "\n" + text[closing:]
    if updated != text:
        migration.engine.base.atomic_write_text(path, updated)


def patch_server(job: migration.RuntimeJob, strings) -> None:
    configure_duration_overrides()
    skill_blocks = []
    for spec in job.skills:
        block = migration.server_skill_block(spec)
        configured_action = migration.legacy_action(job, spec)
        block = block.replace(configured_action, legacy_action(spec), 1)
        if spec.target_id in (
                FREEZING_BREATH_TARGET_ID,
                SPIRIT_OF_SNOW_TARGET_ID, SPIRIT_OF_SNOW_TICK_TARGET_ID,
        ):
            for name, value in (
                    ("attackCount", spec.attack_count),
                    ("cooltime", spec.cooldown),
                    ("damage", spec.damage),
                    ("mad", spec.damage),
                    ("mobCount", spec.mob_count),
                    ("mpCon", spec.mp_con),
            ):
                block = re.sub(
                    rf'(<int name="{name}" value=")-?\d+("/>)',
                    rf'\g<1>{value}\g<2>', block,
                )
            block = re.sub(
                r'<vector name="lt" x="-?\d+" y="-?\d+"/>',
                f'<vector name="lt" x="{spec.lt[0]}" y="{spec.lt[1]}"/>', block,
            )
            block = re.sub(
                r'<vector name="rb" x="-?\d+" y="-?\d+"/>',
                f'<vector name="rb" x="{spec.rb[0]}" y="{spec.rb[1]}"/>', block,
            )
            if spec.target_id == FREEZING_BREATH_TARGET_ID:
                block = re.sub(
                    r'(<int name="time" value=")-?\d+("/>)',
                    rf'\g<1>{spec.duration_seconds}\g<2>', block,
                )
        if spec.target_id == CHAIN_TARGET_ID:
            block = block.replace(
                '<vector name="lt" x="-700" y="-500"/>',
                f'<vector name="lt" x="{spec.lt[0]}" y="{spec.lt[1]}"/>',
            ).replace(
                '<vector name="rb" x="700" y="300"/>',
                f'<vector name="rb" x="{spec.rb[0]}" y="{spec.rb[1]}"/>',
            )
        prop = {
            CHAIN_TARGET_ID: 100,
            MAIN_TARGET_ID: 70,
            PASSIVE_TARGET_ID: 70,
        }.get(spec.target_id)
        if prop is not None:
            prop_line = f'        <int name="prop" value="{prop}"/>'
            block = block.replace(
                '        <int name="mpCon"', prop_line + '\n        <int name="mpCon"'
            )
        skill_blocks.append(block)
    replace_xml_blocks(
        migration.engine.SERVER_SKILL, "skill",
        (*REMOVED_SKILL_IDS, *(spec.target_id for spec in job.skills)), skill_blocks,
    )

    visible_specs = [spec for spec in job.skills if not spec.hidden]
    string_blocks = []
    for spec in visible_specs:
        source = migration.engine.source_string_values(strings, spec.source_id)
        if spec.target_id == FREEZING_BREATH_TARGET_ID:
            source = {**source, "desc": "释放极寒吐息冻结前方敌人。"}
        block = migration.engine.server_string_block(spec, source)
        if spec.target_id == FREEZING_BREATH_TARGET_ID:
            level_text = (
                "消耗MP 22，最多攻击8名敌人，以80%伤害攻击4次，"
                "冻结13秒，无冷却时间"
            )
            block = re.sub(
                r'(<string name="h\d+" value=")[^"]*("/>)',
                rf'\g<1>{level_text}\g<2>',
                block,
            )
        string_blocks.append(block)
    replace_xml_blocks(
        migration.SERVER_STRING, None,
        (*REMOVED_STRING_IDS, *(spec.target_id for spec in visible_specs)), string_blocks,
    )


def validate() -> None:
    migration.validate_job()
    root = WzImage.from_bytes(
        migration.engine.CLIENT_SKILL.read_bytes(),
        key=WzKey.for_region("GMS"),
        name=migration.engine.CLIENT_SKILL.name,
    ).parse()
    names = tuple(child.name for child in root.get("skill").children())
    expected = BASE_SKILL_IDS + CUSTOM_SKILL_IDS
    if names != expected:
        raise RuntimeError(f"client skill whitelist mismatch: {names} != {expected}")
    effect = WzImage.from_bytes(
        migration.engine.CLIENT_MAP_EFFECT.read_bytes(),
        key=WzKey.for_region("GMS"),
        name=migration.engine.CLIENT_MAP_EFFECT.name,
    ).parse()
    for target_id in (FROZEN_LIGHTNING_TARGET_ID, PARABOLIC_VOLT_TARGET_ID):
        marker = effect.get(f"customSkill/ilArchMage/video{target_id}/0")
        if not isinstance(marker, WzCanvasProperty) or (marker.width, marker.height) != (7, 5):
            raise RuntimeError(f"missing Ice/Lightning MCV marker: {target_id}")


def main() -> int:
    job = runtime_job()
    record, strings = build_client_record(job)
    old_count, new_count = patch_client_skill(record)
    strings_changed = synchronize_client_strings()
    string_values_changed = patch_client_string_values()
    marker_changed = reactivate_effect_marker()
    patch_server(job, strings)
    validate()
    RETIRED_ICE_AGE_VIDEO.unlink(missing_ok=True)
    print(f"client skill visible count: {old_count} -> {new_count}")
    print(f"client skill record bytes written: {len(record)}")
    print(f"client string names synchronized in place: {strings_changed}")
    print(f"client string values synchronized in place: {string_values_changed}")
    print(f"Map Effect marker reactivated in place: {marker_changed}")
    print(f"retired Ice Age video removed: {RETIRED_ICE_AGE_VIDEO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

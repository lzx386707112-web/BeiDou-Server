#!/usr/bin/env python3
"""Migrate attack-only TMS V/VI skills for the remaining supported Explorers."""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
sys.path.insert(0, str(PATCH_SKILL))

import patch_blaze_wizard_v_vi as engine  # noqa: E402

# Importing the Wind Archer helper configures the shared engine module and
# replaces its build_skill function. Keep the neutral builder before that
# side effect so Explorer jobs do not inherit Wind Archer's weapon=45 limit.
BASE_BUILD_SKILL = engine.build_skill
import patch_wind_archer_v_vi as wind_compat  # noqa: E402
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.writer import (  # noqa: E402
    _encode_property_list,
    encode_compressed_int,
    re_encrypt_string,
)


TMS_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
MS_EXPORT_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-MS-Export/ExplorerOther")
STRING_JSON = TMS_ROOT / "String" / "Skill.img.json"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
CLIENT_MAP_EFFECT = ROOT / "clien" / "Data" / "Map" / "Effect.img"
LEGACY_ARROW_RAIN_SOURCE = ROOT / "clien" / "Data" / "Skill" / "311.img"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"
MASTER_LEVEL = 30
SHADOWER_LEGACY_BASELINE = "db6b6b4a51"
SHADOWER_LOWER_JOB_SKILL_IDS = (
    4200000, 4200001, 4201002, 4201003, 4201004, 4201005,
    4210000, 4211001, 4211002, 4211003, 4211004, 4211005, 4211006,
    4220002, 4220005, 4221000, 4221001, 4221003, 4221004,
    4221006, 4221007, 4221008,
)
SHADOWER_LOWER_JOB_STRING_IDS = SHADOWER_LOWER_JOB_SKILL_IDS
SHADOWER_SKILL_BOOK_STRING_IDS = (
    2280006, 2290080, 2290081, 2290082, 2290083,
    2290090, 2290091, 2290092, 2290093,
)
SHADOWER_SERVER_SKILL_STRINGS = (
    ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml",
    ROOT / "gms-server" / "wz-zh-CN" / "String.wz" / "Skill.img.xml",
)
SHADOWER_SERVER_CONSUME_STRINGS = (
    ROOT / "gms-server" / "wz" / "String.wz" / "Consume.img.xml",
    ROOT / "gms-server" / "wz-zh-CN" / "String.wz" / "Consume.img.xml",
)


def git_blob(revision: str, relative_path: str) -> bytes:
    return subprocess.run(
        ["git", "cat-file", "blob", f"{revision}:{relative_path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


@dataclass(frozen=True)
class JobConfig:
    key: str
    book: int
    vi_group: str
    v_group: str
    v_ids: tuple[int, ...]
    active_v_ids: frozenset[int]
    target_start: int
    action: str
    elem_attr: str | None
    magic: bool


@dataclass(frozen=True)
class RuntimeJob:
    config: JobConfig
    skills: tuple[engine.SkillSpec, ...]
    source_by_target: dict[int, int]
    target_by_source: dict[int, int]


JOBS = (
    JobConfig("fpArchMage", 212, "214", "40002",
              (400021001, 400021028, 400021029, 400021066,
               400021101, 400021102, 400021103),
              frozenset({400021001, 400021028, 400021066, 400021101}),
              2121009, "fireDemon", "f", True),
    JobConfig("ilArchMage", 222, "224", "40002",
              (400021002, 400021030, 400021031, 400021040,
               400021067, 400021094, 400021112),
              frozenset({400021002, 400021030, 400021067, 400021094}),
              2221009, "iceDemon", "i", True),
    JobConfig("bishop", 232, "234", "40002",
              (400021032, 400021033, 400021070, 400021077, 400021086),
              frozenset({400021032, 400021070, 400021086}),
              2321020, "holyarrow", "h", True),
    JobConfig("bowmaster", 312, "314", "40003",
              (400031002, 400031020, 400031021, 400031028,
               400031029, 400031053, 400031054),
              frozenset({400031002, 400031020, 400031028, 400031053}),
              3121010, "shoot1", None, False),
    JobConfig("marksman", 322, "324", "40003",
              (400031006, 400031010, 400031015, 400031016,
               400031025, 400031055, 400031056),
              frozenset({400031006, 400031015, 400031025, 400031055}),
              3221009, "shoot2", None, False),
    JobConfig("nightLord", 412, "414", "40004",
              (400041001, 400041020, 400041038, 400041059, 400041060),
              frozenset({400041001, 400041020, 400041038, 400041059}),
              4121010, "shoot1", None, False),
    JobConfig("shadower", 422, "436", "40004",
              (400041006, 400041021, 400041042, 400041043,
               400041075, 400041076, 400041077, 400041078),
              frozenset({400041006, 400041021, 400041042}),
              4221009, "stabO1", None, False),
    JobConfig("buccaneer", 512, "514", "40005",
              (400051002, 400051003, 400051015, 400051042,
               400051070, 400051071),
              frozenset({400051002, 400051015, 400051042, 400051070}),
              5121011, "swingO1", None, False),
    JobConfig("corsair", 522, "524", "40005",
              (400051006, 400051021, 400051040, 400051049,
               400051050, 400051073, 400051081),
              frozenset({400051006, 400051021, 400051040, 400051073}),
              5221011, "shot", None, False),
)


PARAMETER_SOURCE_IDS = {
    400021032: 400021033,
    400021030: 400021031,
    400031055: 400031056,
    400041025: 400041026,
}
PARAMETER_FIELDS = {
    400031002: {"damage": "q", "attackCount": "w", "mobCount": "z"},
}
# Modern Skill.wz reuses `time` for damage, animation milliseconds, projectile
# lifetime, and actual duration. The legacy server interprets level/time only as
# seconds, so overloaded fields need explicit semantic conversion.
DURATION_OVERRIDES = {
    400021094: 40,
    400031021: None,
    3141004: 60,
    3241000: None,
    3241001: None,
    3241003: None,
    5141000: 10,
    5141002: None,
    400051021: None,
    400051040: None,
    # These fields describe a short channel window or buff in modern TMS, not
    # a legacy attack-duration stat. Their repeated damage is scheduled by the
    # server from explicit replay stages instead.
    400041006: None,
    4361001: None,
    4361500: None,
    4361501: None,
}
SHADOWER_DUAL_BLADE_SOURCE_IDS = (
    400041006, 400041021, 400041042, 400041043,
    400041075, 400041076, 400041077, 400041078,
    4360006, 4361000, 4361001, 4361003, 4361004, 4361005,
    4361500, 4361501, 4361502, 4361503, 4361504, 4361505, 4361506,
)
SHADOWER_DUAL_BLADE_ACTIVE_SOURCE_IDS = frozenset({
    400041006, 400041021, 400041042,
    4361000, 4361001, 4361003, 4361005, 4361500, 4361504,
})
SHADOWER_DUAL_BLADE_HIDDEN_DAMAGE_FIELDS = {
    400041075: ("z", "u", "y"),
}
SHADOWER_DUAL_BLADE_RANGE_OVERRIDES = {
    # The legacy projection is larger than the modern logical bounds. Cover
    # the visible projected effect instead of clipping valid targets.
    4361000: ((-550, -370), (210, 160)),
    4361003: ((-350, -270), (380, 105)),
    400041042: ((-270, -450), (285, 45)),
    # shootobj starts at (0, -185), has a 200x370 body, and travels 550px left.
    400041043: ((-650, -370), (100, 0)),
}
SHADOWER_DUAL_BLADE_RETIRED_SKILL_IDS = tuple(range(4221030, 4221041))
SHADOWER_DUAL_BLADE_MANAGED_SKILL_IDS = tuple(range(4221009, 4221030))
IL_EXCLUDED_VI_IDS = frozenset({2241002, 2241007, 2241008, 2241009})
BISHOP_RETIRED_SOURCE_IDS = frozenset({
    400021070, 400021077, 2341000, 2341001, 2341002, 2341003, 2341013,
})
BOWMASTER_RETIRED_SOURCE_IDS = frozenset({
    400031020, 400031021, 400031028, 400031029, 400031053, 400031054,
    3141000, 3141001, 3141004,
})
BOWMASTER_RETIRED_SKILL_IDS = (
    3121011, 3121012, 3121013, 3121014, 3121015, 3121016,
    3121020, 3121021, 3121024,
)
NIGHT_LORD_RETIRED_SOURCE_IDS = frozenset({
    400041001, 400041038, 400041059, 400041060, 4140011, 4141007,
})
NIGHT_LORD_RETIRED_SKILL_IDS = (
    4121010, 4121012, 4121013, 4121014, 4121015, 4121021,
)
NIGHT_LORD_CLIENT_REPLACEMENT_IDS = (
    4121011, *range(4121016, 4121021), *range(4121022, 4121030),
)
NIGHT_LORD_PROJECTILE_IDS = frozenset({
    4121011, 4121016, 4121017, 4121019, 4121020, 4121026, 4121027,
})
NIGHT_LORD_BULLET_COUNTS = {
    4121011: 1,
    4121016: 4,
    4121017: 4,
    4121019: 6,
    4121020: 6,
    4121026: 5,
    4121027: 5,
}
BOWMASTER_FLASH_MIRAGE_IDS = (3121026, 3121027)
BOWMASTER_ARROW_RAIN_TICK_ID = 3121033
BOWMASTER_ARROW_RAIN_FIELD_DURATION_MS = 2500
BOWMASTER_CLIENT_REPLACEMENT_IDS = (
    3121010, 3121025, *BOWMASTER_FLASH_MIRAGE_IDS,
)
BOWMASTER_CLIENT_ADDITIONS = (BOWMASTER_ARROW_RAIN_TICK_ID,)
BOWMASTER_SERVER_REPLACEMENT_IDS = (3121010, 3121025)
BOWMASTER_SERVER_ADDITIONS = (BOWMASTER_ARROW_RAIN_TICK_ID,)
MARKSMAN_RETIRED_SOURCE_IDS = frozenset({
    400031015, 400031016, 400031055, 400031056, 3240014,
    3241000, 3241001, 3241002, 3241003, 3241004,
    3241005, 3241006, 3241007, 3241008, 3241009, 3241010, 3241011,
})
MARKSMAN_RETIRED_SKILL_IDS = (
    3221011, 3221012, *range(3221014, 3221029),
)
MARKSMAN_TRUE_SNIPING_IDS = (3221009, 3221010)
MARKSMAN_TRUE_SNIPING_SOURCE_IDS = frozenset({400031006, 400031010})
MARKSMAN_TRUE_SNIPING_LT = (-700, -400)
MARKSMAN_TRUE_SNIPING_RB = (700, 400)
MARKSMAN_CLIENT_REPLACEMENT_IDS = (
    3221013, *range(3221029, 3221036),
)
MARKSMAN_SERVER_REPLACEMENT_IDS = MARKSMAN_CLIENT_REPLACEMENT_IDS
MARKSMAN_PROJECTILE_IDS = frozenset({3221013})
MARKSMAN_FROST_PREY_ID = 3221029
MARKSMAN_FROST_PREY_SUMMON_ACTIONS = (
    ("summoned", "summon/summoned"),
    ("fly", "summon/move"),
    ("stand", "summon/stand"),
    ("attack1", "summon/attack1"),
    ("die", "summon/die"),
)
MARKSMAN_FROST_PREY_SUMMON_INFO = ((-560, -200), (100, 50), 0, 360, 6)
MARKSMAN_HIT_VARIANT_METADATA = {
    3221031: (1, 15, 1, 1),
}
BUCCANEER_RETIRED_SOURCE_IDS = frozenset({
    400051002, 400051003, 400051015,
    5141000, 5141002, 5141003, 5141006, 5141008,
})
BUCCANEER_RETIRED_SKILL_IDS = (
    5121011, 5121012, 5121013,
    5121019, 5121020, 5121021, 5121022, 5121023,
)
BUCCANEER_CLIENT_REPLACEMENT_IDS = (
    5121014, 5121015, 5121016, 5121017, 5121025, 5121026, 5121027,
)
BUCCANEER_SERVER_REPLACEMENT_IDS = (
    5121015, 5121016, 5121017, 5121025, 5121026, 5121027,
)
BUCCANEER_SEA_DRAGON_V_SOURCE_ID = 5121023
BUCCANEER_SEA_DRAGON_V_LT = (-840, -190)
BUCCANEER_SEA_DRAGON_V_RB = (10, 50)
BUCCANEER_HOWLING_FIST_ACTIVE_ID = 5121015
BUCCANEER_HOWLING_FIST_FINISH_ID = 5121016
BUCCANEER_HOWLING_FIST_VIDEO_MARKER = "video5121015"
BUCCANEER_SEA_DRAGON_CHARGE_ID = 5121014
BUCCANEER_SEA_DRAGON_V_ID = 5121017
BUCCANEER_SERPENT_STONE_ID = 5121025
BUCCANEER_SERPENT_ASSAULT_ID = 5121026
BUCCANEER_SERPENT_RAGE_ID = 5121027
BUCCANEER_SERPENT_ASSAULT_HIT_METADATA = {
    "useZ": 1,
    "z": 2,
    "randomHitOrigin": 35,
    "randomHitAngle": 1,
    "hitAfter": -180,
    "delayShowDamage": 300,
}
CORSAIR_RETIRED_SOURCE_IDS = frozenset({
    400051073, 400051081, 5241000, 5241001, 5241002, 5241003,
    5241015, 5241017,
})
CORSAIR_RETIRED_SKILL_IDS = (
    5221016, 5221017, 5221018, 5221019, 5221020, 5221021,
    5221028, 5221029,
)
CORSAIR_DEATH_EYE_VIDEO_MARKER = "video5221012"
IL_LEGACY_ACTIONS = {
    400021002: "blizzard",
    400021030: "chainlightning",
    400021031: "chainlightning",
    400021040: "chainlightning",
    400021067: "alert2",
    400021094: "chainlightning",
    400021112: "chainlightning",
}
IL_HIT_SOURCE_IDS = {
    400021030: 400021031,
}
BISHOP_HIT_SOURCE_IDS = {
    400021032: 400021033,
}
BOWMASTER_HIT_SOURCE_IDS = {
    3141013: 3141014,
}
BOWMASTER_LEGACY_ACTIONS = {
    3141012: "alert2",
}
BOWMASTER_PHOENIX_SUMMON_ACTIONS = (
    ("summoned", "summon/summoned"),
    ("fly", "summon/move"),
    ("stand", "summon/stand"),
    ("attack1", "summon/attack1"),
    ("die", "summon/die"),
)
BOWMASTER_PHOENIX_SUMMON_INFO = ((-560, -200), (100, 50), 0, 720, 6)
BISHOP_COOLDOWN_OVERRIDES = {
    # The v83 level schema only accepts whole cooldown seconds.
    400021086: 2,
}
BISHOP_DIVINE_PUNISHMENT_REPLAY_ID = 2321044
BISHOP_LEGACY_ACTIONS = {
    400021032: "alert2",
    2341006: "alert2",
    # The legacy genesis action delays damage until its full effect finishes.
    # chainlightning is the proven early-impact magic path used by the IL fix.
    2341009: "chainlightning",
    2341011: "chainlightning",
}
BISHOP_PROJECTILE_TRACKS = {}
BISHOP_SUMMON_ACTIONS = {
    400021032: (
        ("summoned", 400021032, "summon/summoned"),
        ("stand", 400021032, "summon/stand"),
        ("fly", 400021032, "summon/move"),
        ("attack1", 400021033, "summon/attack1"),
        ("die", 400021033, "summon/die"),
    ),
    2341006: (
        ("summoned", 2341006, "summon/summoned"),
        ("stand", 2341006, "summon/stand"),
        ("attack1", 2341006, "summon/attack1"),
        ("die", 2341006, "summon/die"),
    ),
}
BISHOP_SUMMON_INFO = {
    # Project modern summon metadata onto the four fields consumed by the
    # legacy summon attack path. Values come from the matching TMS XML nodes;
    # Fountain uses common/attackDelay because its attack1 has no attackAfter.
    # Legacy following magic summons only support six targets per automatic
    # attack; feeding the modern 12-target value into this path locks the
    # client when Angel of Balance performs its first attack.
    400021032: ((-640, -210), (0, 30), 0, 660, 6),
    2341006: ((-290, -300), (290, 110), 0, 2000, 8),
}
BISHOP_CLIENT_REPLACEMENTS = {
    2321020: ("summon", "action", "hit"),
    2321024: ("effect",),
    2321031: ("summon", "action"),
    2321032: (),
    2321033: ("action",),
    2321035: ("action", "effect", "special"),
}
BISHOP_CLIENT_ADDITIONS = (BISHOP_DIVINE_PUNISHMENT_REPLAY_ID,)
BISHOP_SERVER_REPLACEMENTS = tuple(BISHOP_CLIENT_REPLACEMENTS)
# The v83 client only understands the legacy summon action names below. The
# modern Ice Age and Jupiter Thunder field objects are projected onto that
# structure so their persistent visuals can be spawned by the server.
IL_LEGACY_SUMMONS = {
    400021002: (
        ("summoned", "special3", 0),
        ("stand", "special2", 0),
        ("attack1", "special", 0),
        ("die", "special3", 0),
    ),
    400021067: (
        ("summoned", "summon/summoned", 0),
        ("stand", "summon/stand", 0),
        ("attack1", "summon/attack1", 0),
        ("die", "summon/die", 0),
    ),
    400021094: (
        ("summoned", "ball", 0),
        ("stand", "ball", 0),
        ("attack1", "special", 0),
        ("die", "ball", 0),
    ),
}
IL_LINKED_LEGACY_SUMMONS = frozenset({400021002, 400021094})
EFFECT_CANDIDATES = (
    "effect", "effect0", "effect1", "effect2", "effect3", "effect4",
    "keydown", "keydown0", "repeat", "repeat0", "start", "start0",
)
EXTRA_CANDIDATES = (
    "prepare", "prepare0", "prepare2", "keydownend", "keydownend0",
    "keydownend2", "keydownFinish", "end", "end0", "special", "special0",
    "special1", "special2", "special3", "mob", "tile", "number", "affected",
    "hit2", "effectFlash", "rush",
)
PROJECTILE_CANDIDATES = ("ball", "shootobj", "SecondAtom")


CURRENT_JOB: RuntimeJob | None = None
ORIGINAL_BUILD_SKILL = BASE_BUILD_SKILL
ORIGINAL_TRACKS = engine.tracks


def expression_value(value: str | None, default: int = 0, level: int = MASTER_LEVEL) -> int:
    if value is None:
        return default
    value = re.sub(r"(?<=\d)(?=(?:d|u|log(?:10|20|30))\()", "*", value)
    return int(eval(value, {"__builtins__": {}}, {
        "x": level,
        "d": math.floor,
        "u": math.ceil,
        "min": min,
        "max": max,
        "log10": lambda value: int(value >= 10),
        "log20": lambda value: int(value >= 20),
        "log30": lambda value: int(value >= 30),
    }))


def named_child(node: ET.Element | None, name: str) -> ET.Element | None:
    if node is None:
        return None
    return next((child for child in node if child.get("name") == name), None)


def scalar(
    node: ET.Element | None,
    name: str,
    default: int = 0,
    level: int = MASTER_LEVEL,
) -> int:
    child = named_child(node, name)
    return expression_value(None if child is None else child.get("value"), default, level)


def vector(node: ET.Element | None, name: str, default: tuple[int, int]) -> tuple[int, int]:
    child = named_child(node, name)
    if child is None or child.tag != "vector":
        return default
    return int(child.get("x")), int(child.get("y"))


def has_renderable_canvas(node: ET.Element | None) -> bool:
    if node is None:
        return False
    for canvas in node.iter("canvas"):
        if int(canvas.get("width", "1")) > 1 or int(canvas.get("height", "1")) > 1:
            return True
        if any(child.get("name") == "_outlink" for child in canvas):
            return True
    return False


def linked_icon_source(root: ET.Element, default: int) -> int:
    icon = named_child(root, "icon")
    if icon is None:
        return default
    outlink = next((child.get("value", "") for child in icon
                    if child.get("name") == "_outlink"), "")
    match = re.search(r"/skill/(\d+)/icon$", outlink)
    return int(match.group(1)) if match else default


def exported_roots() -> dict[int, ET.Element]:
    roots = {}
    for path in MS_EXPORT_ROOT.glob("*.xml"):
        root = ET.parse(path).getroot()
        roots[int(root.get("id"))] = root
    return roots


def source_names() -> dict[int, str]:
    document = json.loads(STRING_JSON.read_text(encoding="utf-8"))
    names = {}
    for node in document["children"]:
        if not node["name"].isdigit():
            continue
        name = next((child.get("value", "") for child in node.get("children", [])
                     if child["name"] == "name"), "")
        names[int(node["name"])] = name
    return names


def vi_ids(config: JobConfig, roots: dict[int, ET.Element]) -> list[int]:
    if config.key == "shadower":
        return [
            source_id for source_id in SHADOWER_DUAL_BLADE_SOURCE_IDS
            if source_id >= 4360000
        ]
    return sorted(
        skill_id for skill_id, root in roots.items()
        if root.get("sourceGroup") == config.vi_group
    )


def make_spec(
    config: JobConfig,
    source_id: int,
    target_id: int,
    active: bool,
    roots: dict[int, ET.Element],
    names: dict[int, str],
) -> engine.SkillSpec | None:
    root = roots.get(source_id)
    if root is None:
        raise RuntimeError(f"missing exported source metadata: {source_id}")
    parameter_id = PARAMETER_SOURCE_IDS.get(source_id, source_id)
    parameter_root = roots[parameter_id]
    own_common = named_child(root, "common")
    parameter_common = named_child(parameter_root, "common")
    fields = PARAMETER_FIELDS.get(source_id, {})
    if config.key == "shadower" and source_id in SHADOWER_DUAL_BLADE_HIDDEN_DAMAGE_FIELDS:
        damage_field, attack_field, mob_field = (
            SHADOWER_DUAL_BLADE_HIDDEN_DAMAGE_FIELDS[source_id]
        )
        damage = scalar(own_common, damage_field)
        attack_count = max(1, scalar(own_common, attack_field, 1))
        mob_count = max(1, scalar(own_common, mob_field, 1))
    else:
        damage = scalar(parameter_common, fields.get("damage", "damage"))
        attack_count = max(1, scalar(
            parameter_common, fields.get("attackCount", "attackCount"), 1
        ))
        mob_count = max(1, scalar(
            parameter_common, fields.get("mobCount", "mobCount"), 1
        ))
    if damage <= 0 and not active:
        return None
    if damage <= 0:
        raise RuntimeError(f"active attack has no damage parameter: {source_id}")
    top_names = {child.get("name") for child in root}
    if "keydown" in top_names:
        effects = tuple(name for name in ("keydown", "keydown0") if name in top_names)
    else:
        effects = tuple(name for name in EFFECT_CANDIDATES if name in top_names)[:2]
    extras = tuple(name for name in EXTRA_CANDIDATES if name in top_names and name not in effects)
    projectiles = tuple(name for name in PROJECTILE_CANDIDATES if name in top_names)
    duration = (DURATION_OVERRIDES[source_id]
                if source_id in DURATION_OVERRIDES else scalar(own_common, "time"))
    spec = engine.SkillSpec(
        target_id=target_id,
        source_id=source_id,
        source_group=root.get("sourceGroup"),
        name=names.get(source_id, str(source_id)),
        damage=damage,
        attack_count=min(15, attack_count),
        mob_count=min(15, mob_count),
        mp_con=scalar(own_common, "mpCon"),
        cooldown=BISHOP_COOLDOWN_OVERRIDES.get(
            source_id, scalar(own_common, "cooltime")
        ),
        hidden=not active,
        icon_source_id=linked_icon_source(root, parameter_id),
        effect_nodes=effects,
        projectile_nodes=projectiles,
        summon_node="summon" if "summon" in top_names else None,
        extra_nodes=extras,
        lt=vector(parameter_common, "lt", (-700, -500)),
        rb=vector(parameter_common, "rb", (700, 300)),
        duration_seconds=duration if duration is not None and duration > 0 else None,
        include_hit=has_renderable_canvas(named_child(root, "hit")),
    )
    if source_id in MARKSMAN_TRUE_SNIPING_SOURCE_IDS:
        spec = replace(
            spec,
            lt=MARKSMAN_TRUE_SNIPING_LT,
            rb=MARKSMAN_TRUE_SNIPING_RB,
        )
    if config.key == "shadower" \
            and source_id in SHADOWER_DUAL_BLADE_RANGE_OVERRIDES:
        lt, rb = SHADOWER_DUAL_BLADE_RANGE_OVERRIDES[source_id]
        spec = replace(spec, lt=lt, rb=rb)
    if config.key == "buccaneer" and source_id == 5140004:
        spec = replace(
            spec,
            effect_source_id=BUCCANEER_SEA_DRAGON_V_SOURCE_ID,
            effect_nodes=("effect",),
            hit_source_id=BUCCANEER_SEA_DRAGON_V_SOURCE_ID,
            include_hit=True,
            lt=BUCCANEER_SEA_DRAGON_V_LT,
            rb=BUCCANEER_SEA_DRAGON_V_RB,
        )
    hit_source_id = (
        IL_HIT_SOURCE_IDS.get(source_id)
        if config.key == "ilArchMage"
        else BISHOP_HIT_SOURCE_IDS.get(source_id)
        if config.key == "bishop"
        else BOWMASTER_HIT_SOURCE_IDS.get(source_id)
        if config.key == "bowmaster"
        else None
    )
    if hit_source_id is not None:
        spec = replace(spec, hit_source_id=hit_source_id, include_hit=True)
    return spec


def build_runtime_jobs() -> tuple[RuntimeJob, ...]:
    roots = exported_roots()
    names = source_names()
    jobs = []
    for config in JOBS:
        source_ids = (
            list(SHADOWER_DUAL_BLADE_SOURCE_IDS)
            if config.key == "shadower"
            else [*config.v_ids, *vi_ids(config, roots)]
        )
        specs = []
        target_id = config.target_start
        for source_id in source_ids:
            root = roots.get(source_id)
            if root is None:
                raise RuntimeError(f"source {source_id} was not exported")
            invisible = named_child(root, "invisible") is not None
            recognizable_il_action = (
                config.key != "ilArchMage" or named_child(root, "action") is not None
            )
            active = source_id in config.active_v_ids or (
                root.get("sourceGroup") == config.vi_group
                and not invisible
                and recognizable_il_action
            )
            if config.key == "shadower":
                active = source_id in SHADOWER_DUAL_BLADE_ACTIVE_SOURCE_IDS
            spec = make_spec(config, source_id, target_id, active, roots, names)
            if spec is not None:
                target_id += 1
                if config.key == "ilArchMage" and source_id in IL_EXCLUDED_VI_IDS:
                    continue
                if config.key == "bishop" and source_id in BISHOP_RETIRED_SOURCE_IDS:
                    continue
                if config.key == "bowmaster" and source_id in BOWMASTER_RETIRED_SOURCE_IDS:
                    continue
                if config.key == "nightLord" and source_id in NIGHT_LORD_RETIRED_SOURCE_IDS:
                    continue
                if config.key == "marksman" and source_id in MARKSMAN_RETIRED_SOURCE_IDS:
                    continue
                if config.key == "buccaneer" and source_id in BUCCANEER_RETIRED_SOURCE_IDS:
                    continue
                if config.key == "corsair" and source_id in CORSAIR_RETIRED_SOURCE_IDS:
                    continue
                specs.append(spec)
        if config.key == "bishop":
            punishment = next(spec for spec in specs if spec.target_id == 2321024)
            specs.append(replace(
                punishment,
                target_id=BISHOP_DIVINE_PUNISHMENT_REPLAY_ID,
                name="神之惩罚：命中",
                mp_con=0,
                cooldown=0,
                hidden=True,
                effect_nodes=(),
                projectile_nodes=(),
                summon_node=None,
                extra_nodes=(),
                duration_seconds=None,
            ))
        if config.key == "bowmaster":
            arrow_rain = next(spec for spec in specs if spec.target_id == 3121010)
            specs.append(replace(
                arrow_rain,
                target_id=BOWMASTER_ARROW_RAIN_TICK_ID,
                name="箭雨：领域攻击",
                mp_con=0,
                cooldown=0,
                hidden=True,
                effect_nodes=(),
                projectile_nodes=(),
                summon_node=None,
                extra_nodes=(),
                duration_seconds=None,
                include_hit=True,
            ))
        source_by_target = {spec.target_id: spec.source_id for spec in specs}
        target_by_source = {}
        for spec in specs:
            target_by_source.setdefault(spec.source_id, spec.target_id)
        jobs.append(RuntimeJob(config, tuple(specs), source_by_target, target_by_source))
    return tuple(jobs)


def multi_attack_schedule(job: RuntimeJob, spec: engine.SkillSpec) -> dict[int, tuple[int, ...]]:
    root = ET.parse(MS_EXPORT_ROOT / f"{spec.source_id}.xml").getroot()
    timeline = named_child(root, "multiAttackInfo")
    elapsed = 0
    grouped: dict[int, list[int]] = {}
    if timeline is not None:
        for phase in timeline:
            elapsed += scalar(phase, "attackTime")
            source_id = scalar(phase, "x", spec.source_id)
            replay_id = job.target_by_source.get(source_id, spec.target_id)
            grouped.setdefault(replay_id, []).append(elapsed)
    if spec.source_id == 4141500:
        controller = ET.parse(MS_EXPORT_ROOT / "4141502.xml").getroot()
        common = named_child(controller, "common")
        duration_ms = scalar(common, "time") * 1000
        interval_ms = scalar(common, "subTime")
        follow_up = controller.find(
            "./imgdir[@name='extraSkillInfo']/imgdir/int[@name='skill']"
        )
        if follow_up is None:
            raise RuntimeError("Forbidden Talisman field controller has no follow-up skill")
        replay_id = job.target_by_source[int(follow_up.get("value"))]
        grouped[replay_id] = list(range(interval_ms, duration_ms, interval_ms))
    return {skill_id: tuple(times) for skill_id, times in grouped.items()}


def legacy_action(job: RuntimeJob, spec: engine.SkillSpec) -> str:
    if job.config.key == "ilArchMage":
        return IL_LEGACY_ACTIONS.get(spec.source_id, job.config.action)
    if job.config.key == "bishop":
        return BISHOP_LEGACY_ACTIONS.get(spec.source_id, job.config.action)
    if job.config.key == "bowmaster":
        return BOWMASTER_LEGACY_ACTIONS.get(spec.source_id, job.config.action)
    return job.config.action


def level_parameters(spec: engine.SkillSpec, level: int) -> dict[str, int | None | tuple[int, int]]:
    root = ET.parse(MS_EXPORT_ROOT / f"{spec.source_id}.xml").getroot()
    parameter_id = PARAMETER_SOURCE_IDS.get(spec.source_id, spec.source_id)
    parameter_root = ET.parse(MS_EXPORT_ROOT / f"{parameter_id}.xml").getroot()
    own_common = named_child(root, "common")
    parameter_common = named_child(parameter_root, "common")
    fields = PARAMETER_FIELDS.get(spec.source_id, {})
    if CURRENT_JOB is not None and CURRENT_JOB.config.key == "shadower" \
            and spec.source_id in SHADOWER_DUAL_BLADE_HIDDEN_DAMAGE_FIELDS:
        damage_field, attack_field, mob_field = (
            SHADOWER_DUAL_BLADE_HIDDEN_DAMAGE_FIELDS[spec.source_id]
        )
        damage = scalar(own_common, damage_field, level=level)
        attack_count = scalar(own_common, attack_field, 1, level)
        mob_count = scalar(own_common, mob_field, 1, level)
    else:
        damage = scalar(
            parameter_common, fields.get("damage", "damage"), level=level
        )
        attack_count = scalar(
            parameter_common, fields.get("attackCount", "attackCount"), 1, level
        )
        mob_count = scalar(
            parameter_common, fields.get("mobCount", "mobCount"), 1, level
        )
    duration = (DURATION_OVERRIDES[spec.source_id]
                if spec.source_id in DURATION_OVERRIDES
                else scalar(own_common, "time", level=level))
    result = {
        "damage": damage,
        "attackCount": min(15, max(1, attack_count)),
        "mobCount": min(15, max(1, mob_count)),
        "mpCon": scalar(own_common, "mpCon", level=level),
        "cooltime": BISHOP_COOLDOWN_OVERRIDES.get(
            spec.source_id, scalar(own_common, "cooltime", level=level)
        ),
        "lt": vector(parameter_common, "lt", (-700, -500)),
        "rb": vector(parameter_common, "rb", (700, 300)),
        "time": duration if duration is not None and duration > 0 else None,
    }
    if spec.source_id in MARKSMAN_TRUE_SNIPING_SOURCE_IDS:
        result["lt"] = MARKSMAN_TRUE_SNIPING_LT
        result["rb"] = MARKSMAN_TRUE_SNIPING_RB
    if spec.source_id == 400041020:
        # shootobj starts at (-180, -58), has a 280x280 body, and travels
        # 600px left before holding. Cover exactly that swept body.
        result["lt"] = (-920, -198)
        result["rb"] = (-40, 82)
    if CURRENT_JOB is not None and CURRENT_JOB.config.key == "shadower" \
            and spec.source_id in SHADOWER_DUAL_BLADE_RANGE_OVERRIDES:
        result["lt"], result["rb"] = (
            SHADOWER_DUAL_BLADE_RANGE_OVERRIDES[spec.source_id]
        )
    if spec.target_id == BISHOP_DIVINE_PUNISHMENT_REPLAY_ID:
        result["mpCon"] = 0
        result["cooltime"] = 0
        result["time"] = None
    if spec.target_id == BOWMASTER_ARROW_RAIN_TICK_ID:
        result["mpCon"] = 0
        result["cooltime"] = 0
        result["time"] = None
    return result


def rewrite_levels(target, spec: engine.SkillSpec) -> None:
    levels = target.child("level")
    for level in range(1, MASTER_LEVEL + 1):
        node = levels.child(str(level))
        values = level_parameters(spec, level)
        for name in ("attackCount", "cooltime", "damage", "mobCount", "mpCon"):
            engine.set_int(node, name, values[name])
        if CURRENT_JOB is not None and CURRENT_JOB.config.magic:
            engine.set_int(node, "mad", values["damage"])
        elif CURRENT_JOB is not None and CURRENT_JOB.config.key == "shadower":
            node._children.pop("mad", None)
            node._children.pop("bulletCount", None)
        engine.set_vector(node, "lt", values["lt"])
        engine.set_vector(node, "rb", values["rb"])
        if values["time"] is None:
            node._children.pop("time", None)
        else:
            engine.set_int(node, "time", values["time"])


def add_legacy_summon(target, key, groups, metadata, spec: engine.SkillSpec) -> None:
    animations = IL_LEGACY_SUMMONS.get(spec.source_id)
    if animations is None:
        return
    summon = engine.WzSubProperty("summon", target)
    for target_name, source_path, variant_index in animations:
        if spec.source_id in IL_LINKED_LEGACY_SUMMONS:
            resolved_path = source_path
            source = target.get(resolved_path)
            frames = engine.base.numeric_canvases(source)
            if not frames:
                resolved_path = f"{source_path}/{variant_index}"
                source = target.get(resolved_path)
                frames = engine.base.numeric_canvases(source)
            if not frames:
                raise RuntimeError(f"missing linked legacy summon track: {spec.source_id}/{source_path}")
            action = engine.WzSubProperty(target_name, summon)
            direct_canvas = (
                target_name in {"summoned", "die"}
                or (spec.source_id == 400021002 and target_name == "stand")
            )
            for frame in frames:
                if direct_canvas:
                    action.add(engine.base.clone_property(frame, frame.name, action))
                else:
                    action.add(engine.WzUolProperty(
                        frame.name,
                        f"../../{resolved_path}/{frame.name}",
                        action,
                    ))
            summon.add(action)
            continue
        variants = engine.tracks(groups, metadata, spec.source_id, source_path)
        if not variants or variant_index >= len(variants):
            raise RuntimeError(f"missing legacy summon track: {spec.source_id}/{source_path}")
        action = engine.WzSubProperty(target_name, summon)
        engine.base.merge_tracks(variants[variant_index], [], action, key)
        summon.add(action)
    target._children.pop("summon", None)
    target.add(summon)


def add_bishop_projectile(target, key, groups, metadata, spec: engine.SkillSpec) -> None:
    paths = BISHOP_PROJECTILE_TRACKS.get(spec.source_id)
    if paths is None:
        return
    frames = []
    for path in paths:
        variants = engine.tracks(groups, metadata, spec.source_id, path)
        if not variants:
            raise RuntimeError(f"missing Bishop projectile track: {spec.source_id}/{path}")
        frames.extend(variants[0])
    ball = engine.WzSubProperty("ball", target)
    engine.base.merge_tracks(frames, [], ball, key)
    target._children.pop("ball", None)
    target.add(ball)


def add_bishop_summon(target, key, groups, metadata, spec: engine.SkillSpec) -> None:
    actions = BISHOP_SUMMON_ACTIONS.get(spec.source_id)
    if actions is None:
        return
    summon = engine.WzSubProperty("summon", target)
    for target_name, source_id, source_path in actions:
        variants = engine.tracks(groups, metadata, source_id, source_path)
        if not variants:
            raise RuntimeError(f"missing Bishop summon track: {source_id}/{source_path}")
        action = engine.WzSubProperty(target_name, summon)
        if target_name == "attack1":
            lt, rb, attack_type, attack_after, mob_count = BISHOP_SUMMON_INFO[spec.source_id]
            info = engine.WzSubProperty("info", action)
            attack_range = engine.WzSubProperty("range", info)
            engine.set_vector(attack_range, "lt", lt)
            engine.set_vector(attack_range, "rb", rb)
            info.add(attack_range)
            engine.set_int(info, "type", attack_type)
            engine.set_int(info, "attackAfter", attack_after)
            engine.set_int(info, "mobCount", mob_count)
            action.add(info)
        engine.base.merge_tracks(variants[0], [], action, key)
        summon.add(action)
    target._children.pop("summon", None)
    target.add(summon)


def merge_branch_variants(target, source_name: str, target_name: str) -> None:
    source = target.child(source_name)
    destination = target.child(target_name)
    if not isinstance(source, engine.WzSubProperty):
        return
    if not isinstance(destination, engine.WzSubProperty):
        source.name = target_name
        target._children.pop(source_name, None)
        target.add(source)
        return
    numeric = [child for child in destination.children() if child.name.isdigit()]
    next_index = max((int(child.name) for child in numeric), default=-1) + 1
    for child in source.children():
        destination.add(engine.base.clone_property(child, str(next_index), destination))
        next_index += 1
    target._children.pop(source_name, None)


def flatten_legacy_mob_animation(target) -> None:
    mob = target.child("mob")
    if not isinstance(mob, engine.WzSubProperty):
        return
    frames = engine.base.numeric_canvases(mob)
    if frames:
        return
    variants = sorted(
        (child for child in mob.children()
         if isinstance(child, engine.WzSubProperty) and child.name.isdigit()),
        key=lambda child: int(child.name),
    )
    if not variants:
        target._children.pop("mob", None)
        return
    frames = engine.base.numeric_canvases(variants[0])
    if not frames:
        target._children.pop("mob", None)
        return
    flattened = engine.WzSubProperty("mob", target)
    for index, frame in enumerate(frames):
        flattened.add(engine.base.clone_property(frame, str(index), flattened))
    target._children.pop("mob", None)
    target.add(flattened)


def normalize_il_legacy_nodes(target) -> None:
    merge_branch_variants(target, "hit2", "hit")
    flatten_legacy_mob_animation(target)
    target._children.pop("special2", None)
    target._children.pop("special3", None)


def replace_flash_mirage_cast_effect(target, key, groups, metadata, spec) -> None:
    aura_variants = engine.tracks(
        groups, metadata, spec.source_id, "effect"
    )
    shot_variants = engine.tracks(
        groups, metadata, spec.source_id, "special"
    )
    if not aura_variants or not shot_variants:
        raise RuntimeError("Flash Mirage requires effect and special tracks")
    aura = aura_variants[0]
    shot = shot_variants[0]
    if len(aura) != 10 or len(shot) != 20:
        raise RuntimeError(
            f"unexpected Flash Mirage cast timeline: {len(aura)}/{len(shot)}"
        )
    effect = engine.WzSubProperty("effect", target)
    engine.base.merge_tracks(aura, shot, effect, key)
    engine.base.replace_child(target, effect)


def encode_legacy_gms_canvas(source, name: str, parent, key):
    with decode_canvas(source, region="GMS") as decoded:
        pixels = decoded.convert("RGBA")
    canvas = engine.WzCanvasProperty(name, parent)
    canvas.width, canvas.height = pixels.size
    canvas.format = 1
    canvas.format2 = 0
    canvas._png_data = encode_canvas_payload(
        pixels, 1, canvas.width, canvas.height,
        key=key, listwz=False, zlib_level=9,
    )
    canvas._png_length = len(canvas._png_data)
    pixels.close()
    origin = source.get("origin")
    if origin is not None:
        engine.set_vector(canvas, "origin", (int(origin.x), int(origin.y)))
    for property_name in ("delay", "z", "a0", "a1"):
        value = source.get(property_name)
        if value is not None:
            engine.set_int(canvas, property_name, int(value.value))
    return canvas


def legacy_arrow_rain_source():
    image = engine.WzImage.from_bytes(
        LEGACY_ARROW_RAIN_SOURCE.read_bytes(),
        key=engine.WzKey.for_region("GMS"),
        name=LEGACY_ARROW_RAIN_SOURCE.name,
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"cannot read legacy Arrow Rain source: {image.parse_warnings}"
        )
    source = root.get("skill/3111004")
    if not isinstance(source, engine.WzSubProperty):
        raise RuntimeError("legacy Arrow Rain skill/3111004 is missing")
    return source


def add_arrow_rain_tick_visuals(target, key, groups, metadata, spec) -> None:
    loop_variants = engine.tracks(
        groups, metadata, spec.source_id, "repeat"
    )
    if not loop_variants or len(loop_variants[0]) != 8:
        raise RuntimeError("Arrow Rain tick requires eight repeat frames")
    effect = engine.WzSubProperty("effect", target)
    engine.base.merge_tracks(loop_variants[0], [], effect, key)
    engine.base.replace_child(target, effect)

    legacy = legacy_arrow_rain_source()
    special_source = legacy.get("special")
    special_canvas = legacy.get("special/0/0")
    if not isinstance(special_source, engine.WzSubProperty) \
            or not isinstance(special_canvas, engine.WzCanvasProperty):
        raise RuntimeError("legacy Arrow Rain special is incomplete")
    special = engine.WzSubProperty("special", target)
    special_zero = engine.WzSubProperty("0", special)
    special_zero.add(encode_legacy_gms_canvas(
        special_canvas, "0", special_zero, key
    ))
    special.add(special_zero)
    for property_name in ("x", "y", "fall", "start", "interval", "count", "duration"):
        value = special_source.get(property_name)
        if value is None:
            raise RuntimeError(f"legacy Arrow Rain special/{property_name} is missing")
        engine.set_int(special, property_name, int(value.value))
    engine.base.replace_child(target, special)

    hit_source = legacy.get("hit/0")
    hit_frames = engine.base.numeric_canvases(hit_source)
    if len(hit_frames) != 3:
        raise RuntimeError("legacy Arrow Rain hit requires three frames")
    hit = engine.WzSubProperty("hit", target)
    hit_zero = engine.WzSubProperty("0", hit)
    for index, source in enumerate(hit_frames):
        hit_zero.add(encode_legacy_gms_canvas(
            source, str(index), hit_zero, key
        ))
    hit.add(hit_zero)
    engine.base.replace_child(target, hit)


def replace_arrow_rain_effect(target, key, groups, metadata, spec) -> None:
    intro_variants = engine.tracks(
        groups, metadata, spec.source_id, "effect"
    )
    loop_variants = engine.tracks(
        groups, metadata, spec.source_id, "repeat"
    )
    if not intro_variants or not loop_variants:
        raise RuntimeError("Arrow Rain requires effect and repeat tracks")
    intro = intro_variants[0]
    loop = loop_variants[0]
    if len(intro) != 15 or len(loop) != 8:
        raise RuntimeError(
            f"unexpected Arrow Rain tracks: {len(intro)}/{len(loop)}"
        )
    duration = BOWMASTER_ARROW_RAIN_FIELD_DURATION_MS

    effect = engine.WzSubProperty("effect", target)
    elapsed = 0
    loop_names = []
    loop_delays = []
    for canvas, frame_metadata in (*intro, *loop):
        frame = engine.base.encode_target_canvas(
            canvas, str(len(effect.children())), effect, key,
            meta=frame_metadata,
        )
        delay = engine.base.frame_delay(canvas, frame_metadata)
        engine.set_int(frame, "delay", delay)
        effect.add(frame)
        elapsed += delay
        if len(effect.children()) > len(intro):
            loop_names.append(frame.name)
            loop_delays.append(delay)

    loop_index = 0
    while elapsed < duration:
        source_name = loop_names[loop_index]
        delay = loop_delays[loop_index]
        remaining = duration - elapsed
        if remaining >= delay:
            effect.add(engine.WzUolProperty(
                str(len(effect.children())), source_name, effect
            ))
            elapsed += delay
        else:
            canvas, frame_metadata = loop[loop_index]
            frame = engine.base.encode_target_canvas(
                canvas, str(len(effect.children())), effect, key,
                meta=frame_metadata,
            )
            engine.set_int(frame, "delay", remaining)
            effect.add(frame)
            elapsed = duration
        loop_index = (loop_index + 1) % len(loop)
    engine.base.replace_child(target, effect)


def add_bowmaster_phoenix_summon(target, key, groups, metadata, spec) -> None:
    summon = engine.WzSubProperty("summon", target)
    for target_name, source_path in BOWMASTER_PHOENIX_SUMMON_ACTIONS:
        variants = engine.tracks(
            groups, metadata, spec.source_id, source_path
        )
        if not variants:
            raise RuntimeError(
                f"missing Phoenix VI summon track: {spec.source_id}/{source_path}"
            )
        action = engine.WzSubProperty(target_name, summon)
        if target_name == "attack1":
            lt, rb, attack_type, attack_after, mob_count = (
                BOWMASTER_PHOENIX_SUMMON_INFO
            )
            info = engine.WzSubProperty("info", action)
            attack_range = engine.WzSubProperty("range", info)
            engine.set_vector(attack_range, "lt", lt)
            engine.set_vector(attack_range, "rb", rb)
            info.add(attack_range)
            engine.set_int(info, "type", attack_type)
            engine.set_int(info, "attackAfter", attack_after)
            engine.set_int(info, "mobCount", mob_count)
            action.add(info)
        engine.base.merge_tracks(variants[0], [], action, key)
        summon.add(action)
    engine.base.replace_child(target, summon)
    flatten_legacy_mob_animation(target)


def add_level_ball_references(target) -> None:
    ball = target.child("ball")
    if not isinstance(ball, engine.WzSubProperty) \
            or not engine.base.numeric_canvases(ball):
        raise RuntimeError(f"Marksman projectile is missing: {target.name}")
    for level in range(1, MASTER_LEVEL + 1):
        level_node = target.get(f"level/{level}")
        if not isinstance(level_node, engine.WzSubProperty):
            raise RuntimeError(
                f"Marksman projectile level is missing: {target.name}/{level}"
            )
        engine.base.replace_child(
            level_node, engine.WzUolProperty("ball", "../../ball", level_node)
        )


def copy_ms_scalar_metadata(source, target) -> None:
    for child in engine.base.ms_children(source):
        name = child.get("name")
        if not name or name.isdigit():
            continue
        if child.tag in {"int", "short", "long"}:
            engine.set_int(target, name, int(child.get("value")))
        elif child.tag == "string":
            engine.set_string(target, name, child.get("value"))
        elif child.tag == "vector":
            engine.set_vector(
                target, name, (int(child.get("x")), int(child.get("y")))
            )


def source_metadata_node(metadata, skill_id: int, path: str):
    node = metadata.roots[skill_id]
    for segment in path.split("/"):
        node = metadata.child(node, segment)
        if node is None:
            raise RuntimeError(f"missing TMS metadata: {skill_id}/{path}")
    return node


def apply_night_lord_visual_metadata(target, metadata, spec) -> None:
    for name in ("effect", "hit"):
        destination = target.child(name)
        if not isinstance(destination, engine.WzSubProperty):
            continue
        source_names = spec.effect_nodes if name == "effect" else ("hit",)
        sources = [
            source_metadata_node(metadata, spec.source_id, source_name)
            for source_name in source_names
        ]
        for source in sources:
            copy_ms_scalar_metadata(source, destination)
        source = sources[0]
        source_variants = [
            child for child in engine.base.ms_children(source)
            if child.get("name", "").isdigit()
        ]
        source_variants.sort(key=lambda child: int(child.get("name")))
        for index, source_variant in enumerate(source_variants):
            destination_variant = destination.child(str(index))
            if isinstance(destination_variant, engine.WzSubProperty):
                copy_ms_scalar_metadata(
                    metadata.resolve(source_variant), destination_variant
                )


def replace_night_lord_ball_from_track(
    target, key, groups, metadata, source_id: int, path: str, expected: int
) -> None:
    variants = engine.tracks(groups, metadata, source_id, path)
    if len(variants) != 1 or len(variants[0]) != expected:
        raise RuntimeError(
            f"unexpected Night Lord projectile: {source_id}/{path}"
        )
    ball = engine.WzSubProperty("ball", target)
    engine.base.merge_tracks(variants[0], [], ball, key)
    engine.base.replace_child(target, ball)


def replace_fuma_shuriken_effect(target, key, groups, metadata) -> None:
    source_root = metadata.roots[400041020]
    indexed_tracks = []
    for node_name in ("effect", "effect0"):
        node = metadata.child(source_root, node_name)
        frames = {}
        for child in engine.base.ms_children(node):
            name = child.get("name", "")
            if not name.isdigit() or child.tag not in {"canvas", "uol"}:
                continue
            resolved = metadata.resolve(child)
            canvas = engine.base.resolve_ms_canvas(resolved, groups, metadata)
            if canvas is not None:
                frames[int(name)] = (canvas, resolved)
        indexed_tracks.append(frames)
    if tuple(map(len, indexed_tracks)) != (7, 11):
        raise RuntimeError("unexpected Fuma Shuriken cast layers")
    effect = engine.WzSubProperty("effect", target)
    for index in range(13):
        primary = indexed_tracks[0].get(index)
        secondary = indexed_tracks[1].get(index)
        if primary is not None and secondary is not None:
            frame = engine.base.compose_frames(
                primary, secondary, str(index), effect, key
            )
        else:
            canvas, meta = primary or secondary
            frame = engine.base.encode_target_canvas(
                canvas, str(index), effect, key, meta=meta
            )
        engine.set_int(frame, "delay", 60)
        effect.add(frame)
    engine.base.replace_child(target, effect)


def replace_fuma_shuriken_ball(target, key, groups, metadata) -> None:
    phases = []
    for path, expected in (
        ("shootobj/layerList/b1", 6),
        ("shootobj/layerList/c1", 6),
        ("shootobj/layerList/e1", 18),
    ):
        variants = engine.tracks(groups, metadata, 400041020, path)
        if len(variants) != 1 or len(variants[0]) != expected:
            raise RuntimeError(f"unexpected Fuma Shuriken phase: {path}")
        phases.append(variants[0])

    ball = engine.WzSubProperty("ball", target)
    engine.base.merge_tracks(phases[0], [], ball, key)
    engine.base.replace_child(target, ball)
    target._children.pop("fumaHold", None)

    summon = engine.WzSubProperty("summon", target)
    for state, frames in (
        ("summoned", phases[1]),
        ("stand", phases[1]),
        ("die", phases[2]),
    ):
        action = engine.WzSubProperty(state, summon)
        engine.base.merge_tracks(frames, [], action, key)
        summon.add(action)
    engine.base.replace_child(target, summon)


def replace_night_lord_ball_variant(
    target, key, groups, metadata, source_id: int, path: str,
    variant_index: int, expected: int,
) -> None:
    variants = engine.tracks(groups, metadata, source_id, path)
    if variant_index >= len(variants) or len(variants[variant_index]) != expected:
        raise RuntimeError(
            f"unexpected Night Lord projectile variant: {source_id}/{path}"
        )
    ball = engine.WzSubProperty("ball", target)
    engine.base.merge_tracks(variants[variant_index], [], ball, key)
    engine.base.replace_child(target, ball)


def add_night_lord_projectile(target, key, groups, metadata, spec) -> None:
    if spec.target_id == 4121011:
        replace_fuma_shuriken_ball(target, key, groups, metadata)
    elif spec.target_id in {4121016, 4121017}:
        # Project the complete TMS Quad Star VI streak onto the legacy flat
        # ball renderer. The old ball/0 projection kept only half the track.
        replace_night_lord_ball_from_track(
            target, key, groups, metadata,
            4141001, "shootobj/layerList/b1", 16,
        )
    elif spec.target_id in {4121019, 4121020}:
        wind_compat.add_second_atom_projectile(target, key, 73, 7)
    elif spec.target_id in {4121026, 4121027}:
        # TMS uses b1/b2/b3 as angle-specific views of one projectile. The
        # legacy flat ball contract has no angle selector, so retain the full
        # centered b2 loop and let the native destination hook aim each copy.
        replace_night_lord_ball_from_track(
            target, key, groups, metadata,
            4141501, "shootobj/layerList/b2", 6,
        )
    if spec.target_id in NIGHT_LORD_PROJECTILE_IDS:
        add_level_ball_references(target)


def add_marksman_projectile(target, key, groups, metadata, spec) -> None:
    source_path = "ball" if spec.source_id == 3241005 else "shootobj/layerList/b1"
    variants = engine.tracks(groups, metadata, spec.source_id, source_path)
    if not variants:
        raise RuntimeError(
            f"missing Marksman projectile track: {spec.source_id}/{source_path}"
        )
    ball = engine.WzSubProperty("ball", target)
    engine.base.merge_tracks(variants[0], [], ball, key)
    engine.base.replace_child(target, ball)


def apply_marksman_hit_metadata(target) -> None:
    values = MARKSMAN_HIT_VARIANT_METADATA.get(int(target.name))
    if values is None:
        return
    random_hit, random_origin, use_z, z = values
    hit = target.child("hit")
    if not isinstance(hit, engine.WzSubProperty):
        raise RuntimeError(f"Marksman hit node is missing: {target.name}")
    engine.set_int(hit, "randomHit", random_hit)
    variants = [
        child for child in hit.children()
        if isinstance(child, engine.WzSubProperty) and child.name.isdigit()
    ]
    if not variants:
        raise RuntimeError(f"Marksman hit variants are missing: {target.name}")
    metadata_variants = variants[:3] if int(target.name) == 3221031 else variants
    for variant in metadata_variants:
        engine.set_int(variant, "randomHitOrigin", random_origin)
        if use_z is not None:
            engine.set_int(variant, "useZ", use_z)
        if z is not None:
            engine.set_int(variant, "z", z)


def add_marksman_frost_prey_summon(target, key, groups, metadata, spec) -> None:
    summon = engine.WzSubProperty("summon", target)
    for target_name, source_path in MARKSMAN_FROST_PREY_SUMMON_ACTIONS:
        variants = engine.tracks(groups, metadata, spec.source_id, source_path)
        if not variants:
            raise RuntimeError(
                f"missing Frostprey VI summon track: {spec.source_id}/{source_path}"
            )
        action = engine.WzSubProperty(target_name, summon)
        if target_name == "attack1":
            lt, rb, attack_type, attack_after, mob_count = (
                MARKSMAN_FROST_PREY_SUMMON_INFO
            )
            info = engine.WzSubProperty("info", action)
            attack_range = engine.WzSubProperty("range", info)
            engine.set_vector(attack_range, "lt", lt)
            engine.set_vector(attack_range, "rb", rb)
            info.add(attack_range)
            engine.set_int(info, "type", attack_type)
            engine.set_int(info, "attackAfter", attack_after)
            engine.set_int(info, "mobCount", mob_count)
            action.add(info)
        engine.base.merge_tracks(variants[0], [], action, key)
        summon.add(action)
    engine.base.replace_child(target, summon)


def replace_buccaneer_howling_fist_charge_effect(
        target, key, groups, metadata, spec) -> None:
    effect = engine.WzSubProperty("effect", target)
    output_index = 0
    for node_names in (("prepare", "prepare0"), ("keydown", "keydown0")):
        primary, secondary = engine.paired_tracks(
            groups, metadata, spec.source_id, node_names
        )
        if not primary and not secondary:
            raise RuntimeError(
                f"missing Howling Fist charge phase: {spec.source_id}/{node_names[0]}"
            )
        engine.base.merge_tracks(
            primary, secondary, effect, key, start_index=output_index
        )
        output_index += max(len(primary), len(secondary))
    engine.base.replace_child(target, effect)
    target._children.pop("prepare", None)
    target._children.pop("prepare0", None)


def replace_buccaneer_howling_fist_finish_special(
        target, key, groups, metadata, spec) -> None:
    bms_key = engine.WzKey.for_region("BMS")
    pair_nodes = (("effect", "special"), ("screen", "screen0"))
    merged_pairs = []
    for pair_index, node_names in enumerate(pair_nodes):
        primary, secondary = engine.paired_tracks(
            groups, metadata, spec.source_id, node_names
        )
        if not primary and not secondary:
            raise RuntimeError(
                f"missing Howling Fist finish layer: {spec.source_id}/{node_names[0]}"
            )
        temporary = engine.WzSubProperty(str(pair_index), None)
        engine.base.merge_tracks(primary, secondary, temporary, bms_key)
        merged_pairs.append([
            (frame, None) for frame in engine.base.numeric_canvases(temporary)
        ])

    special = engine.WzSubProperty("special", target)
    variant = engine.WzSubProperty("0", special)
    engine.base.merge_tracks(
        merged_pairs[0], merged_pairs[1], variant, key
    )
    for frame in engine.base.numeric_canvases(variant):
        image = decode_canvas(frame, region="GMS").convert("RGBA")
        width, height, fit_scale = engine.base.fit_size(
            image.width * 2, image.height * 2
        )
        resized = image.resize((width, height), Image.Resampling.LANCZOS)
        image.close()
        origin = frame.get("origin")
        overall_scale = 2 * fit_scale
        frame.width = width
        frame.height = height
        frame._png_data = encode_canvas_payload(
            resized, 1, width, height, key=key, listwz=False, zlib_level=9
        )
        resized.close()
        frame._png_length = len(frame._png_data)
        engine.set_vector(
            frame,
            "origin",
            (round(int(origin.x) * overall_scale),
             round(int(origin.y) * overall_scale)),
        )
    special.add(variant)
    engine.base.replace_child(target, special)
    target._children.pop("effect", None)


def add_buccaneer_serpent_rage_effect(target, key) -> None:
    wind_compat.add_second_atom_projectile(target, key, 78, 12)
    ball = target.child("ball")
    if not isinstance(ball, engine.WzSubProperty):
        raise RuntimeError("Serpent Rage VI projectile is missing")
    engine.base.replace_child(
        target, engine.base.clone_property(ball, "effect", target)
    )


def configured_backup(path: Path) -> None:
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    target = path.with_name(path.name + f".bak-{CURRENT_JOB.config.key}-v-vi")
    if not target.exists():
        shutil.copy2(path, target)
        print(f"backup: {target}")


def referenced_canvas_groups(job: RuntimeJob) -> set[str]:
    groups = {job.config.vi_group, job.config.v_group}
    if job.config.key == "buccaneer":
        groups.add("512")
    for source_id in job.source_by_target.values():
        text = (MS_EXPORT_ROOT / f"{source_id}.xml").read_text(encoding="utf-8")
        groups.update(re.findall(r"Skill/_Canvas/(\d+)\.img/", text))
    return groups


def project_true_sniping_marker_to_hit(target) -> None:
    special = target.child("special")
    marker = special.child("0") if isinstance(special, engine.WzSubProperty) else None
    if not isinstance(marker, engine.WzSubProperty) \
            or len(engine.base.numeric_canvases(marker)) != 7:
        raise RuntimeError("True Sniping requires the seven-frame target marker")
    hit = engine.base.clone_property(special, "hit", target)
    target._children.pop("special", None)
    target.add(hit)


def build_skill(spec, parent, key, groups, metadata):
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    target = ORIGINAL_BUILD_SKILL(spec, parent, key, groups, metadata)
    engine.set_string(target.child("action"), "0", legacy_action(CURRENT_JOB, spec))
    rewrite_levels(target, spec)
    if CURRENT_JOB.config.key == "shadower":
        for name in ("weapon", "weapon2", "subWeapon"):
            target._children.pop(name, None)
    if CURRENT_JOB.config.key == "ilArchMage":
        add_legacy_summon(target, key, groups, metadata, spec)
        normalize_il_legacy_nodes(target)
    elif CURRENT_JOB.config.key == "bishop":
        add_bishop_projectile(target, key, groups, metadata, spec)
        add_bishop_summon(target, key, groups, metadata, spec)
        if spec.source_id == 2341007:
            for level in target.child("level").children():
                engine.set_int(level, "x", -44)
                engine.set_int(level, "prop", 100)
    elif CURRENT_JOB.config.key == "bowmaster":
        if spec.target_id == 3121010:
            replace_arrow_rain_effect(
                target, key, groups, metadata, spec
            )
        elif spec.target_id == BOWMASTER_ARROW_RAIN_TICK_ID:
            add_arrow_rain_tick_visuals(
                target, key, groups, metadata, spec
            )
        elif spec.target_id == 3121025:
            add_bowmaster_phoenix_summon(
                target, key, groups, metadata, spec
            )
        elif spec.target_id in BOWMASTER_FLASH_MIRAGE_IDS:
            wind_compat.add_second_atom_projectile(target, key, 80, 12)
            wind_compat.set_hit_variant_metadata(
                target, random_origin=35, random_angle=1, use_z=1, z=1
            )
            if spec.target_id == 3121026:
                replace_flash_mirage_cast_effect(
                    target, key, groups, metadata, spec
                )
    elif CURRENT_JOB.config.key == "marksman":
        if spec.target_id == 3221009:
            project_true_sniping_marker_to_hit(target)
        elif spec.target_id == MARKSMAN_FROST_PREY_ID:
            add_marksman_frost_prey_summon(
                target, key, groups, metadata, spec
            )
        elif spec.target_id == 3221031:
            merge_branch_variants(target, "hit2", "hit")
            repeated_hit = target.get("hit/3")
            if not isinstance(repeated_hit, engine.WzSubProperty):
                raise RuntimeError("Long Range True Shot VI repeated hit is missing")
            engine.set_int(repeated_hit, "repeat", 15)
        if spec.target_id in MARKSMAN_PROJECTILE_IDS:
            add_marksman_projectile(target, key, groups, metadata, spec)
            add_level_ball_references(target)
        apply_marksman_hit_metadata(target)
    elif CURRENT_JOB.config.key == "nightLord":
        # The old client already validates the Night Lord attack path. A
        # top-level weapon restriction inherited from another profession makes
        # claw-equipped characters fail locally with "equipment mismatch".
        for name in ("weapon", "weapon2", "subWeapon"):
            target._children.pop(name, None)
        if spec.target_id == 4121011:
            replace_fuma_shuriken_effect(
                target, key, groups, metadata
            )
        add_night_lord_projectile(target, key, groups, metadata, spec)
        apply_night_lord_visual_metadata(target, metadata, spec)
        bullet_count = NIGHT_LORD_BULLET_COUNTS.get(spec.target_id)
        if bullet_count is not None:
            for level in range(1, MASTER_LEVEL + 1):
                engine.set_int(
                    target.get(f"level/{level}"), "bulletCount", bullet_count
                )
    elif CURRENT_JOB.config.key == "buccaneer":
        if spec.target_id == BUCCANEER_SEA_DRAGON_CHARGE_ID:
            engine.set_string(target.child("action"), "0", "rush2")
        elif spec.target_id == BUCCANEER_HOWLING_FIST_ACTIVE_ID:
            replace_buccaneer_howling_fist_charge_effect(
                target, key, groups, metadata, spec
            )
        elif spec.target_id == BUCCANEER_HOWLING_FIST_FINISH_ID:
            replace_buccaneer_howling_fist_finish_special(
                target, key, groups, metadata, spec
            )
        elif spec.target_id == BUCCANEER_SERPENT_ASSAULT_ID:
            hit = target.get("hit/0")
            if not isinstance(hit, engine.WzSubProperty):
                raise RuntimeError("Serpent Assault VI hit/0 is missing")
            for property_name, value in BUCCANEER_SERPENT_ASSAULT_HIT_METADATA.items():
                engine.set_int(hit, property_name, value)
        elif spec.target_id == BUCCANEER_SERPENT_RAGE_ID:
            add_buccaneer_serpent_rage_effect(target, key)
        if spec.target_id in BUCCANEER_CLIENT_REPLACEMENT_IDS:
            target._children.pop("weapon", None)
            target._children.pop("weapon2", None)
    if CURRENT_JOB.config.elem_attr is None:
        target._children.pop("elemAttr", None)
    else:
        engine.set_string(target, "elemAttr", CURRENT_JOB.config.elem_attr)
    if CURRENT_JOB.config.key == "bowmaster" and spec.target_id == 3121025:
        engine.set_string(target, "elemAttr", "f")
        engine.set_int(target, "weapon", 45)
    elif CURRENT_JOB.config.key == "marksman" \
            and spec.target_id == MARKSMAN_FROST_PREY_ID:
        engine.set_string(target, "elemAttr", "i")
        engine.set_int(target, "weapon", 46)
        for level in target.child("level").children():
            engine.set_int(level, "pad", int(level.get("damage").value))
            engine.set_int(level, "x", 3)
    return target


def source_node(groups, skill_id: int):
    for group in groups.values():
        node = group.get(f"skill/{skill_id}")
        if isinstance(node, engine.WzSubProperty):
            return node
    raise RuntimeError(f"missing source skill/{skill_id}")


def source_tracks(groups, metadata, skill_id: int, node_name: str):
    if skill_id not in metadata.roots:
        path = MS_EXPORT_ROOT / f"{skill_id}.xml"
        root = ET.parse(path).getroot()
        if root.tag != "skill" or int(root.get("id", 0)) != skill_id:
            raise RuntimeError(f"invalid auxiliary MS skill export: {path}")
        metadata.roots[skill_id] = root

        def visit(element: ET.Element, node_path: str) -> None:
            metadata.paths[id(element)] = node_path
            metadata.index[node_path] = element
            for child in element:
                name = child.get("name")
                if name is not None:
                    visit(child, f"{node_path}/{name}")

        visit(root, f"skill/{skill_id}")
    source = source_node(groups, skill_id)
    meta = metadata.roots[skill_id]
    for segment in node_name.split("/"):
        source = source.child(segment) if isinstance(source, engine.WzSubProperty) else None
        meta = metadata.child(meta, segment)
    return engine.base.effect_tracks(
        source if isinstance(source, engine.WzSubProperty) else None,
        meta,
        groups,
        metadata,
    )


def server_skill_block(spec: engine.SkillSpec) -> str:
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    lines = [f'  <imgdir name="{spec.target_id}">', '    <imgdir name="action">',
             f'      <string name="0" value="{legacy_action(CURRENT_JOB, spec)}"/>', "    </imgdir>",
             '    <imgdir name="level">']
    for level in range(1, MASTER_LEVEL + 1):
        parameter_level = MASTER_LEVEL if CURRENT_JOB.config.key == "bishop" else level
        values = level_parameters(spec, parameter_level)
        lines.extend([
            f'      <imgdir name="{level}">',
            f'        <int name="attackCount" value="{values["attackCount"]}"/>',
            f'        <int name="cooltime" value="{values["cooltime"]}"/>',
            f'        <int name="damage" value="{values["damage"]}"/>',
            *([f'        <int name="mad" value="{values["damage"]}"/>'] if CURRENT_JOB.config.magic else []),
            *([f'        <int name="pad" value="{values["damage"]}"/>']
              if spec.target_id in {3121025, MARKSMAN_FROST_PREY_ID} else []),
            f'        <string name="hs" value="h{level}"/>',
            f'        <vector name="lt" x="{values["lt"][0]}" y="{values["lt"][1]}"/>',
            f'        <int name="mobCount" value="{values["mobCount"]}"/>',
            f'        <int name="mpCon" value="{values["mpCon"]}"/>',
            f'        <vector name="rb" x="{values["rb"][0]}" y="{values["rb"][1]}"/>',
            *(['        <int name="x" value="-44"/>',
               '        <int name="prop" value="100"/>']
              if spec.source_id == 2341007 else []),
            *(['        <int name="x" value="3"/>']
              if spec.target_id == MARKSMAN_FROST_PREY_ID else []),
            *([f'        <int name="time" value="{values["time"]}"/>']
              if values["time"] is not None else []),
            "      </imgdir>",
        ])
    lines.extend(["    </imgdir>", f'    <int name="masterLevel" value="{MASTER_LEVEL}"/>'])
    if CURRENT_JOB.config.elem_attr is not None:
        lines.append(f'    <string name="elemAttr" value="{CURRENT_JOB.config.elem_attr}"/>')
    elif CURRENT_JOB.config.key == "bowmaster" and spec.target_id == 3121025:
        lines.append('    <string name="elemAttr" value="f"/>')
    elif CURRENT_JOB.config.key == "marksman" \
            and spec.target_id == MARKSMAN_FROST_PREY_ID:
        lines.append('    <string name="elemAttr" value="i"/>')
    if spec.hidden:
        lines.append('    <int name="invisible" value="1"/>')
    lines.append("  </imgdir>")
    return "\n".join(lines)


def patch_server_skill(dry_run: bool) -> None:
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    path = engine.SERVER_SKILL
    text = path.read_text(encoding="utf-8")
    if CURRENT_JOB.config.key == "shadower":
        updated = remove_server_skill_blocks(
            text,
            (*SHADOWER_DUAL_BLADE_MANAGED_SKILL_IDS,
             *SHADOWER_DUAL_BLADE_RETIRED_SKILL_IDS),
        )
        start, end = engine.find_imgdir_block(updated, "skill")
        closing = updated.rfind("</imgdir>", start, end)
        if closing < 0:
            raise RuntimeError(f"missing skill closing node: {path}")
        blocks = "\n".join(server_skill_block(spec) for spec in CURRENT_JOB.skills)
        # The source XML mixes compact and indented records. Anchor the
        # generated block after the previous sibling instead of before the
        # closing tag's existing indentation, otherwise every run accumulates
        # another copy of that whitespace and changes the file hash.
        prefix = updated[:closing].rstrip()
        updated = prefix + "\n" + blocks + "\n" + updated[closing:]
    elif CURRENT_JOB.config.key == "bowmaster":
        updated = remove_server_skill_blocks(text, BOWMASTER_RETIRED_SKILL_IDS)
        specs = {spec.target_id: spec for spec in CURRENT_JOB.skills}
        for skill_id in BOWMASTER_SERVER_REPLACEMENT_IDS:
            start, end = engine.find_imgdir_block(updated, str(skill_id))
            replacement = server_skill_block(specs[skill_id]).lstrip()
            updated = updated[:start] + replacement + updated[end:]
        for skill_id in BOWMASTER_SERVER_ADDITIONS:
            replacement = server_skill_block(specs[skill_id]).lstrip()
            if f'<imgdir name="{skill_id}">' in updated:
                start, end = engine.find_imgdir_block(updated, str(skill_id))
                updated = updated[:start] + replacement + updated[end:]
            else:
                start, end = engine.find_imgdir_block(updated, "skill")
                closing = updated.rfind("</imgdir>", start, end)
                if closing < 0:
                    raise RuntimeError(f"missing skill closing node: {path}")
                updated = updated[:closing] + replacement + "\n" + updated[closing:]
    elif CURRENT_JOB.config.key == "marksman":
        updated = remove_server_skill_blocks(text, MARKSMAN_RETIRED_SKILL_IDS)
        specs = {spec.target_id: spec for spec in CURRENT_JOB.skills}
        for skill_id in (*MARKSMAN_TRUE_SNIPING_IDS, *MARKSMAN_SERVER_REPLACEMENT_IDS):
            start, end = engine.find_imgdir_block(updated, str(skill_id))
            replacement = server_skill_block(specs[skill_id]).lstrip()
            updated = updated[:start] + replacement + updated[end:]
    elif CURRENT_JOB.config.key == "nightLord":
        updated = remove_server_skill_blocks(text, NIGHT_LORD_RETIRED_SKILL_IDS)
        specs = {spec.target_id: spec for spec in CURRENT_JOB.skills}
        for skill_id in NIGHT_LORD_CLIENT_REPLACEMENT_IDS:
            start, end = engine.find_imgdir_block(updated, str(skill_id))
            replacement = server_skill_block(specs[skill_id]).lstrip()
            updated = updated[:start] + replacement + updated[end:]
    elif CURRENT_JOB.config.key == "buccaneer":
        updated = remove_server_skill_blocks(text, BUCCANEER_RETIRED_SKILL_IDS)
        specs = {spec.target_id: spec for spec in CURRENT_JOB.skills}
        for skill_id in BUCCANEER_SERVER_REPLACEMENT_IDS:
            start, end = engine.find_imgdir_block(updated, str(skill_id))
            replacement = server_skill_block(specs[skill_id]).lstrip()
            updated = updated[:start] + replacement + updated[end:]
    elif CURRENT_JOB.config.key == "corsair":
        updated = remove_server_skill_blocks(text, CORSAIR_RETIRED_SKILL_IDS)
    elif CURRENT_JOB.config.key == "bishop":
        updated = text
        specs = {spec.target_id: spec for spec in CURRENT_JOB.skills}
        for skill_id in BISHOP_SERVER_REPLACEMENTS:
            start, end = engine.find_imgdir_block(updated, str(skill_id))
            replacement = server_skill_block(specs[skill_id]).lstrip()
            updated = updated[:start] + replacement + updated[end:]
        replay_id = BISHOP_DIVINE_PUNISHMENT_REPLAY_ID
        replacement = server_skill_block(specs[replay_id]).lstrip()
        if f'<imgdir name="{replay_id}">' in updated:
            start, end = engine.find_imgdir_block(updated, str(replay_id))
            updated = updated[:start] + replacement + updated[end:]
        else:
            start, end = engine.find_imgdir_block(updated, "skill")
            closing = updated.rfind("</imgdir>", start, end)
            if closing < 0:
                raise RuntimeError(f"missing skill closing node: {path}")
            updated = updated[:closing] + replacement + "\n" + updated[closing:]
    else:
        for skill_id in engine.CUSTOM_SKILL_IDS:
            text = engine.remove_xml_block(text, str(skill_id))
        start, end = engine.find_imgdir_block(text, "skill")
        closing = text.rfind("</imgdir>", start, end)
        if closing < 0:
            raise RuntimeError(f"missing skill closing node: {path}")
        blocks = "\n".join(server_skill_block(spec) for spec in CURRENT_JOB.skills)
        updated = text[:closing] + blocks + "\n" + text[closing:]
    if not dry_run:
        configured_backup(path)
        engine.base.atomic_write_text(path, updated)


def remove_server_skill_blocks(text: str, skill_ids: tuple[int, ...]) -> str:
    spans = []
    for skill_id in skill_ids:
        try:
            start, end = engine.find_imgdir_block(text, str(skill_id))
        except RuntimeError:
            continue
        line_start = text.rfind("\n", 0, start) + 1
        if not text[line_start:start].strip():
            start = line_start
        if end < len(text) and text[end] == "\n":
            end += 1
        spans.append((start, end))
    for start, end in sorted(spans, reverse=True):
        text = text[:start] + text[end:]
    return text


def locate_client_skill_records(image, path: Path):
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError(f"unsupported standalone IMG header: {path}")
    reader.skip(2)
    root_count = reader.read_compressed_int()
    for _ in range(root_count):
        name = reader.read_string_block(0)
        tag = reader.read_byte()
        if tag != 9:
            raise RuntimeError(f"unexpected root property tag: {name}/{tag}")
        block_size_offset = reader.position
        block_size = reader.read_u32()
        block_start = reader.position
        block_end = block_start + block_size
        if name != "skill":
            reader.seek(block_end)
            continue
        if reader.read_string_block(0) != "Property":
            raise RuntimeError("client Bishop skill root is not a Property")
        reader.skip(2)
        count_offset = reader.position
        count = reader.read_compressed_int()
        count_end = reader.position
        names = []
        records = []
        for _ in range(count):
            start = reader.position
            child_name = reader.read_string_block(0)
            child_tag = reader.read_byte()
            if child_tag != 9:
                raise RuntimeError(f"unexpected Bishop skill tag: {child_name}/{child_tag}")
            child_size = reader.read_u32()
            reader.seek(reader.position + child_size)
            names.append(child_name)
            records.append((start, reader.position))
        if reader.position != block_end:
            raise RuntimeError("client Bishop skill records do not fill the final block")
        return (block_size_offset, block_size, count_offset, count_end,
                tuple(names), tuple(records))
    raise RuntimeError("client 232.img has no skill root")


def encode_incremental_record(node, image) -> bytes:
    encoded = _encode_property_list((node,), image.wz_file.reader)
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError("unexpected incremental property record prefix")
    return encoded[len(prefix):]


def restore_shadower_lower_job_client_skills(dry_run: bool) -> None:
    for book in (420, 421):
        path = ROOT / "clien" / "Data" / "Skill" / f"{book}.img"
        baseline = git_blob(
            SHADOWER_LEGACY_BASELINE, str(path.relative_to(ROOT))
        )
        verified = engine.WzImage.from_bytes(
            baseline, key=engine.WzKey.for_region("GMS"), name=path.name
        )
        verified.parse()
        if verified.truncated or verified.parse_warnings:
            raise RuntimeError(f"malformed Shadower legacy baseline: {path}")
        if not dry_run:
            engine.base.atomic_write_bytes(path, baseline)

    path = ROOT / "clien" / "Data" / "Skill" / "422.img"
    original = path.read_bytes()
    baseline = git_blob(
        SHADOWER_LEGACY_BASELINE, str(path.relative_to(ROOT))
    )
    current_image = engine.WzImage.from_bytes(
        original, key=engine.WzKey.for_region("GMS"), name=path.name
    )
    baseline_image = engine.WzImage.from_bytes(
        baseline, key=engine.WzKey.for_region("GMS"), name=f"baseline-{path.name}"
    )
    current_root = current_image.parse()
    baseline_image.parse()
    if current_image.truncated or current_image.parse_warnings:
        raise RuntimeError(f"malformed current Shadower IMG: {path}")
    (_, _, count_offset, count_end,
     current_names, current_spans) = locate_client_skill_records(current_image, path)
    (_, _, _, _, baseline_names,
     baseline_spans) = locate_client_skill_records(baseline_image, path)
    current_records = {
        int(name): original[start:end]
        for name, (start, end) in zip(current_names, current_spans)
    }
    baseline_records = {
        int(name): baseline[start:end]
        for name, (start, end) in zip(baseline_names, baseline_spans)
    }
    replacements = {
        skill_id: baseline_records[skill_id]
        for skill_id in SHADOWER_LOWER_JOB_SKILL_IDS
        if skill_id // 10000 == 422
    }
    rebuilt = b"".join(
        replacements.get(int(name), current_records[int(name)])
        for name in current_names
    )
    records_start, records_end = current_spans[0][0], current_spans[-1][1]
    updated = bytearray(original[:records_start] + rebuilt + original[records_end:])
    size_delta = len(rebuilt) - (records_end - records_start)
    size_offset = locate_client_skill_records(current_image, path)[0]
    struct.pack_into(
        "<I", updated, size_offset,
        struct.unpack_from("<I", original, size_offset)[0] + size_delta,
    )
    carrier = current_root.child("dualBladeSkin")
    if carrier is not None:
        from patch_shadower_dual_blade_skin import locate_root_records

        image_after_skill = engine.WzImage.from_bytes(
            bytes(updated), key=engine.WzKey.for_region("GMS"), name=path.name
        )
        root_count_offset, root_count_size, root_names, root_spans = (
            locate_root_records(image_after_skill, bytes(updated), path)
        )
        index = root_names.index("dualBladeSkin")
        start, end = root_spans[index]
        del updated[start:end]
        new_count = encode_compressed_int(len(root_names) - 1)
        if len(new_count) != root_count_size:
            raise RuntimeError("Shadower root count width changed")
        updated[root_count_offset:root_count_offset + root_count_size] = new_count
    verified = engine.WzImage.from_bytes(
        bytes(updated), key=engine.WzKey.for_region("GMS"), name=path.name
    )
    root = verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(f"restored Shadower IMG is malformed: {verified.parse_warnings}")
    if root.child("dualBladeSkin") is not None:
        raise RuntimeError("lower-job Dual Blade carrier remains")
    if not dry_run:
        engine.base.atomic_write_bytes(path, bytes(updated))


def restore_fixed_client_string_records(
    path: Path, record_ids: tuple[int, ...], dry_run: bool
) -> None:
    from patch_shadower_dual_blade_skin import locate_root_records

    original = path.read_bytes()
    baseline = git_blob(
        SHADOWER_LEGACY_BASELINE, str(path.relative_to(ROOT))
    )
    current_image = engine.WzImage.from_bytes(
        original, key=engine.WzKey.for_region("GMS"), name=path.name
    )
    baseline_image = engine.WzImage.from_bytes(
        baseline, key=engine.WzKey.for_region("GMS"), name=f"baseline-{path.name}"
    )
    current_image.parse()
    baseline_image.parse()
    _, _, current_names, current_spans = locate_root_records(
        current_image, original, path
    )
    _, _, baseline_names, baseline_spans = locate_root_records(
        baseline_image, baseline, path
    )
    current = {
        name: (start, end) for name, (start, end) in zip(current_names, current_spans)
    }
    source = {
        name: baseline[start:end]
        for name, (start, end) in zip(baseline_names, baseline_spans)
    }
    updated = bytearray(original)
    for record_id in record_ids:
        name = str(record_id)
        start, end = current[name]
        record = source[name]
        if len(record) != end - start:
            raise RuntimeError(f"legacy string span changed: {path}/{record_id}")
        updated[start:end] = record
    if not dry_run:
        engine.base.atomic_write_bytes(path, bytes(updated))


def replace_baseline_xml_blocks(
    path: Path, block_ids: tuple[int, ...], dry_run: bool
) -> None:
    text = path.read_text(encoding="utf-8")
    baseline = git_blob(
        SHADOWER_LEGACY_BASELINE, str(path.relative_to(ROOT))
    ).decode("utf-8")
    replacements = []
    for block_id in block_ids:
        current_start, current_end = engine.find_imgdir_block(text, str(block_id))
        baseline_start, baseline_end = engine.find_imgdir_block(
            baseline, str(block_id)
        )
        replacements.append(
            (current_start, current_end, baseline[baseline_start:baseline_end])
        )
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    if not dry_run:
        engine.base.atomic_write_text(path, text)


def restore_shadower_lower_job_contract(dry_run: bool) -> None:
    restore_shadower_lower_job_client_skills(dry_run)
    restore_fixed_client_string_records(
        CLIENT_STRING, SHADOWER_LOWER_JOB_STRING_IDS, dry_run
    )
    restore_fixed_client_string_records(
        ROOT / "clien" / "Data" / "String" / "Consume.img",
        SHADOWER_SKILL_BOOK_STRING_IDS,
        dry_run,
    )
    for book in (420, 421, 422):
        ids = tuple(
            skill_id for skill_id in SHADOWER_LOWER_JOB_SKILL_IDS
            if skill_id // 10000 == book
        )
        replace_baseline_xml_blocks(
            ROOT / "gms-server" / "wz" / "Skill.wz" / f"{book}.img.xml",
            ids,
            dry_run,
        )
    for path in SHADOWER_SERVER_SKILL_STRINGS:
        replace_baseline_xml_blocks(
            path, SHADOWER_LOWER_JOB_STRING_IDS, dry_run
        )
    for path in SHADOWER_SERVER_CONSUME_STRINGS:
        replace_baseline_xml_blocks(
            path, SHADOWER_SKILL_BOOK_STRING_IDS, dry_run
        )


def patch_shadower_client_skill(groups, metadata, dry_run: bool) -> None:
    if CURRENT_JOB is None or CURRENT_JOB.config.key != "shadower":
        raise RuntimeError("Shadower client patch called for another job")
    path = engine.CLIENT_SKILL
    original = path.read_bytes()
    image = engine.WzImage.from_bytes(
        original, key=engine.WzKey.for_region("GMS"), name=path.name
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"cannot patch malformed {path}: {image.parse_warnings}")
    skill_root = root.get("skill")
    if not isinstance(skill_root, engine.WzSubProperty):
        raise RuntimeError("client 422.img has no skill root")
    (size_offset, old_block_size, count_offset, count_end,
     names, spans) = locate_client_skill_records(image, path)
    raw_records = {
        int(name): original[start:end]
        for name, (start, end) in zip(names, spans)
    }
    specs = {spec.target_id: spec for spec in CURRENT_JOB.skills}
    expected_existing = set(SHADOWER_DUAL_BLADE_MANAGED_SKILL_IDS)
    missing = expected_existing - set(raw_records)
    if missing:
        raise RuntimeError(f"missing existing Shadower V/VI records: {sorted(missing)}")
    replacements = {}
    for skill_id in SHADOWER_DUAL_BLADE_MANAGED_SKILL_IDS:
        generated = build_skill(
            specs[skill_id], skill_root, image.wz_file.reader.key, groups, metadata
        )
        replacements[skill_id] = encode_incremental_record(generated, image)
        print(f"client Dual Blade skill record: {skill_id}")
    retired = set(SHADOWER_DUAL_BLADE_RETIRED_SKILL_IDS)
    retained_records = tuple(
        (name, start, end)
        for name, (start, end) in zip(names, spans)
        if int(name) not in retired
    )
    rebuilt = b"".join(
        replacements.get(int(name), original[start:end])
        for name, start, end in retained_records
    )
    records_start, records_end = spans[0][0], spans[-1][1]
    updated = bytearray(original[:records_start] + rebuilt + original[records_end:])
    new_count = encode_compressed_int(len(retained_records))
    if len(new_count) != count_end - count_offset:
        raise RuntimeError("Shadower skill count encoding size changed")
    updated[count_offset:count_end] = new_count
    struct.pack_into(
        "<I", updated, size_offset,
        old_block_size + len(updated) - len(original),
    )
    for name, (start, end) in zip(names, spans):
        skill_id = int(name)
        if skill_id not in retired and skill_id not in replacements \
                and original[start:end] not in updated:
            raise RuntimeError(f"unchanged Shadower record changed: {skill_id}")
    verified = engine.WzImage.from_bytes(
        bytes(updated), key=engine.WzKey.for_region("GMS"), name=path.name
    )
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(f"patched Shadower IMG is malformed: {verified.parse_warnings}")
    if not dry_run:
        configured_backup(path)
        engine.base.atomic_write_bytes(path, bytes(updated))
    print(
        f"client Shadower records changed={len(replacements)} "
        f"retired={len(set(map(int, names)) & retired)} "
        f"preserved={len(retained_records) - len(replacements)}"
    )


def patch_night_lord_client_skill(groups, metadata, dry_run: bool) -> None:
    if CURRENT_JOB is None or CURRENT_JOB.config.key != "nightLord":
        raise RuntimeError("Night Lord client patch called for another job")
    path = engine.CLIENT_SKILL
    original = path.read_bytes()
    image = engine.WzImage.from_bytes(
        original, key=engine.WzKey.for_region("GMS"), name=path.name
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"cannot patch malformed {path}: {image.parse_warnings}")
    skill_root = root.get("skill")
    if not isinstance(skill_root, engine.WzSubProperty):
        raise RuntimeError("client 412.img has no skill root")
    (size_offset, old_block_size, count_offset, count_end,
     names, spans) = locate_client_skill_records(image, path)
    raw_records = {
        int(name): original[start:end]
        for name, (start, end) in zip(names, spans)
    }
    missing = set(NIGHT_LORD_CLIENT_REPLACEMENT_IDS) - set(raw_records)
    if missing:
        raise RuntimeError(f"missing retained Night Lord records: {sorted(missing)}")
    unexpected_retired = set(NIGHT_LORD_RETIRED_SKILL_IDS) & set(raw_records)
    if unexpected_retired:
        raise RuntimeError(
            f"retired Night Lord records returned: {sorted(unexpected_retired)}"
        )
    specs = {spec.target_id: spec for spec in CURRENT_JOB.skills}
    replacements = {}
    for skill_id in NIGHT_LORD_CLIENT_REPLACEMENT_IDS:
        generated = build_skill(
            specs[skill_id], skill_root, image.wz_file.reader.key, groups, metadata
        )
        replacements[skill_id] = encode_incremental_record(generated, image)
        print(f"client Night Lord skill record: {skill_id}")
    rebuilt = b"".join(
        replacements.get(int(name), original[start:end])
        for name, (start, end) in zip(names, spans)
    )
    records_start, records_end = spans[0][0], spans[-1][1]
    updated = bytearray(
        original[:records_start] + rebuilt + original[records_end:]
    )
    new_count = encode_compressed_int(len(names))
    if len(new_count) != count_end - count_offset:
        raise RuntimeError("Night Lord skill count encoding size changed")
    updated[count_offset:count_end] = new_count
    struct.pack_into(
        "<I", updated, size_offset,
        old_block_size + len(updated) - len(original),
    )
    for name, (start, end) in zip(names, spans):
        skill_id = int(name)
        if skill_id not in replacements and original[start:end] not in updated:
            raise RuntimeError(
                f"unchanged Night Lord record was not preserved: {skill_id}"
            )
    verified = engine.WzImage.from_bytes(
        bytes(updated), key=engine.WzKey.for_region("GMS"), name=path.name
    )
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(
            f"patched Night Lord IMG is malformed: {verified.parse_warnings}"
        )
    if not dry_run:
        configured_backup(path)
        engine.base.atomic_write_bytes(path, bytes(updated))
    print(
        f"client Night Lord records changed={len(replacements)} "
        f"preserved={len(names) - len(replacements)}"
    )


def patch_bowmaster_client_skill(groups, metadata, dry_run: bool) -> None:
    if CURRENT_JOB is None or CURRENT_JOB.config.key != "bowmaster":
        raise RuntimeError("Bowmaster client retirement called for another job")
    path = engine.CLIENT_SKILL
    original = path.read_bytes()
    image = engine.WzImage.from_bytes(
        original, key=engine.WzKey.for_region("GMS"), name=path.name
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"cannot patch malformed {path}: {image.parse_warnings}")
    skill_root = root.get("skill")
    if not isinstance(skill_root, engine.WzSubProperty):
        raise RuntimeError("client 312.img has no skill root")
    (size_offset, old_block_size, count_offset, count_end,
     names, spans) = locate_client_skill_records(image, path)
    raw_records = {
        int(name): original[start:end]
        for name, (start, end) in zip(names, spans)
    }
    retired = {
        skill_id for skill_id in BOWMASTER_RETIRED_SKILL_IDS
        if skill_id in raw_records
    }
    specs = {spec.target_id: spec for spec in CURRENT_JOB.skills}
    replacements = {}
    key = image.wz_file.reader.key
    count_prefix = encode_compressed_int(1)
    managed_ids = (
        *BOWMASTER_CLIENT_REPLACEMENT_IDS,
        *BOWMASTER_CLIENT_ADDITIONS,
    )
    additions = []
    for skill_id in managed_ids:
        generated = build_skill(specs[skill_id], skill_root, key, groups, metadata)
        encoded = _encode_property_list((generated,), image.wz_file.reader)
        if not encoded.startswith(count_prefix):
            raise RuntimeError("unexpected Bowmaster property record prefix")
        record = encoded[len(count_prefix):]
        if skill_id not in raw_records:
            if skill_id not in BOWMASTER_CLIENT_ADDITIONS:
                raise RuntimeError(f"missing existing Bowmaster skill: {skill_id}")
            additions.append(record)
            print(f"client skill record added: {skill_id}")
        else:
            replacements[skill_id] = record
            print(f"client skill record: {skill_id}")
    rebuilt_records = b"".join(
        replacements.get(int(name), original[start:end])
        for name, (start, end) in zip(names, spans)
        if int(name) not in retired
    ) + b"".join(additions)
    records_start, records_end = spans[0][0], spans[-1][1]
    updated = bytearray(original[:records_start] + rebuilt_records + original[records_end:])
    new_count = encode_compressed_int(
        len(names) - len(retired) + len(additions)
    )
    if len(new_count) != count_end - count_offset:
        raise RuntimeError("Bowmaster skill count encoding size changed")
    updated[count_offset:count_end] = new_count
    new_block_size = old_block_size + len(updated) - len(original)
    updated[size_offset:size_offset + 4] = struct.pack("<I", new_block_size)
    if not dry_run:
        configured_backup(path)
        engine.base.atomic_write_bytes(path, bytes(updated))
    print(
        f"client Bowmaster records changed={len(replacements)} "
        f"added={len(additions)} retired={len(retired)} "
        f"preserved={len(names) - len(retired) - len(replacements)}"
    )


def patch_marksman_client_skill(groups, metadata, dry_run: bool) -> None:
    if CURRENT_JOB is None or CURRENT_JOB.config.key != "marksman":
        raise RuntimeError("Marksman client retirement called for another job")
    path = engine.CLIENT_SKILL
    original = path.read_bytes()
    image = engine.WzImage.from_bytes(
        original, key=engine.WzKey.for_region("GMS"), name=path.name
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"cannot patch malformed {path}: {image.parse_warnings}")
    skill_root = root.get("skill")
    if not isinstance(skill_root, engine.WzSubProperty):
        raise RuntimeError("client 322.img has no skill root")
    (size_offset, old_block_size, count_offset, count_end,
     names, spans) = locate_client_skill_records(image, path)
    raw_records = {
        int(name): original[start:end]
        for name, (start, end) in zip(names, spans)
    }
    retired = {
        skill_id for skill_id in MARKSMAN_RETIRED_SKILL_IDS
        if skill_id in raw_records
    }
    specs = {spec.target_id: spec for spec in CURRENT_JOB.skills}
    replacements = {}
    key = image.wz_file.reader.key
    count_prefix = encode_compressed_int(1)
    for skill_id in (*MARKSMAN_TRUE_SNIPING_IDS, *MARKSMAN_CLIENT_REPLACEMENT_IDS):
        if skill_id not in raw_records:
            raise RuntimeError(f"missing existing Marksman skill: {skill_id}")
        generated = build_skill(specs[skill_id], skill_root, key, groups, metadata)
        encoded = _encode_property_list((generated,), image.wz_file.reader)
        if not encoded.startswith(count_prefix):
            raise RuntimeError("unexpected Marksman property record prefix")
        replacements[skill_id] = encoded[len(count_prefix):]
        print(f"client skill record: {skill_id}")
    rebuilt_records = b"".join(
        replacements.get(int(name), original[start:end])
        for name, (start, end) in zip(names, spans)
        if int(name) not in retired
    )
    records_start, records_end = spans[0][0], spans[-1][1]
    updated = bytearray(original[:records_start] + rebuilt_records + original[records_end:])
    new_count = encode_compressed_int(len(names) - len(retired))
    if len(new_count) != count_end - count_offset:
        raise RuntimeError("Marksman skill count encoding size changed")
    updated[count_offset:count_end] = new_count
    new_block_size = old_block_size + len(updated) - len(original)
    updated[size_offset:size_offset + 4] = struct.pack("<I", new_block_size)
    for name, (start, end) in zip(names, spans):
        skill_id = int(name)
        if skill_id not in retired and skill_id not in replacements \
                and original[start:end] not in updated:
            raise RuntimeError(f"unchanged Marksman record was not preserved: {name}")
    if not dry_run:
        configured_backup(path)
        engine.base.atomic_write_bytes(path, bytes(updated))
    print(
        f"client Marksman records changed={len(replacements)} "
        f"retired={len(retired)} "
        f"preserved={len(names) - len(retired) - len(replacements)}"
    )


def patch_buccaneer_client_skill(groups, metadata, dry_run: bool) -> None:
    if CURRENT_JOB is None or CURRENT_JOB.config.key != "buccaneer":
        raise RuntimeError("Buccaneer client patch called for another job")
    path = engine.CLIENT_SKILL
    original = path.read_bytes()
    image = engine.WzImage.from_bytes(
        original, key=engine.WzKey.for_region("GMS"), name=path.name
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"cannot patch malformed {path}: {image.parse_warnings}")
    skill_root = root.get("skill")
    if not isinstance(skill_root, engine.WzSubProperty):
        raise RuntimeError("client 512.img has no skill root")
    (size_offset, old_block_size, count_offset, count_end,
     names, spans) = locate_client_skill_records(image, path)
    raw_records = {
        int(name): original[start:end]
        for name, (start, end) in zip(names, spans)
    }
    retired = {
        skill_id for skill_id in BUCCANEER_RETIRED_SKILL_IDS
        if skill_id in raw_records
    }
    specs = {spec.target_id: spec for spec in CURRENT_JOB.skills}
    replacements = {}
    key = image.wz_file.reader.key
    count_prefix = encode_compressed_int(1)
    for skill_id in BUCCANEER_CLIENT_REPLACEMENT_IDS:
        if skill_id not in raw_records:
            raise RuntimeError(f"missing existing Buccaneer skill: {skill_id}")
        generated = build_skill(specs[skill_id], skill_root, key, groups, metadata)
        encoded = _encode_property_list((generated,), image.wz_file.reader)
        if not encoded.startswith(count_prefix):
            raise RuntimeError("unexpected Buccaneer property record prefix")
        replacements[skill_id] = encoded[len(count_prefix):]
        print(f"client skill record: {skill_id}")
    rebuilt_records = b"".join(
        replacements.get(int(name), original[start:end])
        for name, (start, end) in zip(names, spans)
        if int(name) not in retired
    )
    records_start, records_end = spans[0][0], spans[-1][1]
    updated = bytearray(original[:records_start] + rebuilt_records + original[records_end:])
    new_count = encode_compressed_int(len(names) - len(retired))
    if len(new_count) != count_end - count_offset:
        raise RuntimeError("Buccaneer skill count encoding size changed")
    updated[count_offset:count_end] = new_count
    new_block_size = old_block_size + len(updated) - len(original)
    updated[size_offset:size_offset + 4] = struct.pack("<I", new_block_size)
    for name, (start, end) in zip(names, spans):
        skill_id = int(name)
        if skill_id not in retired and skill_id not in replacements \
                and original[start:end] not in updated:
            raise RuntimeError(f"unchanged Buccaneer record was not preserved: {name}")
    if not dry_run:
        configured_backup(path)
        engine.base.atomic_write_bytes(path, bytes(updated))
    print(
        f"client Buccaneer records changed={len(replacements)} "
        f"retired={len(retired)} "
        f"preserved={len(names) - len(retired) - len(replacements)}"
    )


def patch_corsair_client_skill(dry_run: bool) -> None:
    if CURRENT_JOB is None or CURRENT_JOB.config.key != "corsair":
        raise RuntimeError("Corsair client retirement called for another job")
    path = engine.CLIENT_SKILL
    original = path.read_bytes()
    image = engine.WzImage.from_bytes(
        original, key=engine.WzKey.for_region("GMS"), name=path.name
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"cannot patch malformed {path}: {image.parse_warnings}")
    if not isinstance(root.get("skill"), engine.WzSubProperty):
        raise RuntimeError("client 522.img has no skill root")
    (size_offset, old_block_size, count_offset, count_end,
     names, spans) = locate_client_skill_records(image, path)
    retired = {
        skill_id for skill_id in CORSAIR_RETIRED_SKILL_IDS
        if str(skill_id) in names
    }
    rebuilt_records = b"".join(
        original[start:end]
        for name, (start, end) in zip(names, spans)
        if int(name) not in retired
    )
    records_start, records_end = spans[0][0], spans[-1][1]
    updated = bytearray(original[:records_start] + rebuilt_records + original[records_end:])
    new_count = encode_compressed_int(len(names) - len(retired))
    if len(new_count) != count_end - count_offset:
        raise RuntimeError("Corsair skill count encoding size changed")
    updated[count_offset:count_end] = new_count
    new_block_size = old_block_size + len(updated) - len(original)
    updated[size_offset:size_offset + 4] = struct.pack("<I", new_block_size)
    for name, (start, end) in zip(names, spans):
        if int(name) not in retired and original[start:end] not in updated:
            raise RuntimeError(f"unchanged Corsair record was not preserved: {name}")
    if not dry_run:
        configured_backup(path)
        engine.base.atomic_write_bytes(path, bytes(updated))
    print(
        f"client Corsair records retired={len(retired)} "
        f"preserved={len(names) - len(retired)}"
    )


def locate_nested_property_records(image, data: bytes, parent_path: tuple[str, ...]):
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError(f"unsupported standalone IMG header: {image.name}")
    reader.skip(2)

    def descend(segments: tuple[str, ...], block_end: int, size_offsets: tuple[int, ...]):
        count_offset = reader.position
        count = reader.read_compressed_int()
        count_end = reader.position
        for _ in range(count):
            start = reader.position
            name = reader.read_string_block(0)
            tag = reader.read_byte()
            if tag != 9:
                raise RuntimeError(
                    f"unexpected property tag in {'/'.join(parent_path)}: {name}/{tag}"
                )
            size_offset = reader.position
            block_size = reader.read_u32()
            child_start = reader.position
            child_end = child_start + block_size
            if name != segments[0]:
                reader.seek(child_end)
                continue
            reader.seek(child_start)
            if reader.read_string_block(0) != "Property":
                raise RuntimeError(f"property is not a container: {name}")
            reader.skip(2)
            next_offsets = (*size_offsets, size_offset)
            if len(segments) > 1:
                return descend(segments[1:], child_end, next_offsets)

            child_count_offset = reader.position
            child_count = reader.read_compressed_int()
            child_count_end = reader.position
            names = []
            spans = []
            for _ in range(child_count):
                record_start = reader.position
                child_name = reader.read_string_block(0)
                child_tag = reader.read_byte()
                if child_tag != 9:
                    raise RuntimeError(
                        f"unexpected child tag in {'/'.join(parent_path)}: "
                        f"{child_name}/{child_tag}"
                    )
                child_size = reader.read_u32()
                reader.seek(reader.position + child_size)
                names.append(child_name)
                spans.append((record_start, reader.position))
            if reader.position != child_end:
                raise RuntimeError(
                    f"property records do not fill {'/'.join(parent_path)}"
                )
            return (
                next_offsets,
                child_count_offset,
                child_count_end,
                tuple(names),
                tuple(spans),
                child_end,
            )
        reader.seek(block_end)
        raise RuntimeError(f"missing property path: {'/'.join(parent_path)}")

    return descend(parent_path, len(data), ())


def patch_incremental_map_effect(
    field_root: str,
    marker_name: str,
    dry_run: bool,
) -> None:
    original = CLIENT_MAP_EFFECT.read_bytes()
    image = engine.WzImage.from_bytes(
        original, key=engine.WzKey.for_region("GMS"), name=CLIENT_MAP_EFFECT.name
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"cannot patch malformed {CLIENT_MAP_EFFECT}: {image.parse_warnings}"
        )
    marker_path = f"{field_root}/{marker_name}"
    existing = root.get(marker_path)
    if isinstance(existing, engine.WzSubProperty):
        frame = existing.get("0")
        if not isinstance(frame, engine.WzCanvasProperty) \
                or (int(frame.width), int(frame.height)) != (7, 5):
            raise RuntimeError(f"invalid existing field effect marker: {marker_path}")
        print(f"field effect marker exists: {marker_path}")
        return
    parent = root.get(field_root)
    if not isinstance(parent, engine.WzSubProperty):
        raise RuntimeError(f"missing Map/Effect {field_root}")
    marker = engine.base.build_video_field_marker(
        marker_name,
        parent,
        image.wz_file.reader.key,
    )
    encoded = _encode_property_list((marker,), image.wz_file.reader)
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError("unexpected Map/Effect marker record prefix")
    record = encoded[len(prefix):]
    (size_offsets, count_offset, count_end,
     names, spans, records_end) = locate_nested_property_records(
        image, original, tuple(field_root.split("/"))
    )
    if marker_name in names:
        raise RuntimeError("Map/Effect marker parsed but was not found semantically")
    new_count = encode_compressed_int(len(names) + 1)
    if len(new_count) != count_end - count_offset:
        raise RuntimeError("Map/Effect marker count encoding size changed")
    updated = bytearray(original[:records_end] + record + original[records_end:])
    updated[count_offset:count_end] = new_count
    for size_offset in size_offsets:
        old_size = struct.unpack_from("<I", original, size_offset)[0]
        struct.pack_into("<I", updated, size_offset, old_size + len(record))
    for start, end in spans:
        if original[start:end] not in updated:
            raise RuntimeError("existing Buccaneer Map/Effect marker changed")
    verified = engine.WzImage.from_bytes(
        bytes(updated),
        key=engine.WzKey.for_region("GMS"),
        name=CLIENT_MAP_EFFECT.name,
    )
    verified_root = verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(
            f"patched Map/Effect is malformed: {verified.parse_warnings}"
        )
    frame = verified_root.get(f"{marker_path}/0")
    if not isinstance(frame, engine.WzCanvasProperty) \
            or (int(frame.width), int(frame.height)) != (7, 5):
        raise RuntimeError(f"missing patched field effect marker: {marker_path}")
    if not dry_run:
        engine.base.atomic_write_bytes(CLIENT_MAP_EFFECT, bytes(updated))
    print(f"field effect marker added: {marker_path}")


def patch_buccaneer_map_effect(dry_run: bool) -> None:
    patch_incremental_map_effect(
        "customSkill/buccaneer",
        BUCCANEER_HOWLING_FIST_VIDEO_MARKER,
        dry_run,
    )


def patch_corsair_map_effect(dry_run: bool) -> None:
    patch_incremental_map_effect(
        "customSkill/corsair",
        CORSAIR_DEATH_EYE_VIDEO_MARKER,
        dry_run,
    )


def top_level_name_locations(path: Path):
    image = engine.WzImage.from_file(
        str(path), key=engine.WzKey.for_region("GMS"), name=path.name
    )
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError(f"unsupported standalone IMG header: {path}")
    reader.skip(2)
    count = reader.read_compressed_int()
    locations = {}
    for _ in range(count):
        name, offset, length, encoding, indirected = (
            reader.read_string_block_with_location(0)
        )
        tag = reader.read_byte()
        if tag != 9:
            raise RuntimeError(f"unexpected top-level string tag: {name}/{tag}")
        block_size = reader.read_u32()
        locations[name] = (offset, length, encoding, indirected)
        reader.seek(reader.position + block_size)
    return reader, locations


def patch_bowmaster_client_strings(dry_run: bool) -> None:
    reader, locations = top_level_name_locations(CLIENT_STRING)
    updated = bytearray(CLIENT_STRING.read_bytes())
    changed = 0
    for skill_id in BOWMASTER_RETIRED_SKILL_IDS:
        live_name = str(skill_id)
        retired_name = "b" + live_name[1:]
        location = locations.get(live_name)
        if location is None:
            continue
        if retired_name in locations:
            raise RuntimeError(f"retired client string name already exists: {retired_name}")
        offset, length, encoding, indirected = location
        if indirected:
            raise RuntimeError(f"refusing to patch shared client string name: {live_name}")
        encoded = re_encrypt_string(reader, retired_name, encoding)
        if len(encoded) != length:
            raise RuntimeError(f"client string rename changed byte length: {live_name}")
        updated[offset:offset + length] = encoded
        changed += 1
    if changed and not dry_run:
        configured_backup(CLIENT_STRING)
        engine.base.atomic_write_bytes(CLIENT_STRING, bytes(updated))
    print(f"client Bowmaster strings retired={changed}")


def patch_marksman_client_strings(dry_run: bool) -> None:
    reader, locations = top_level_name_locations(CLIENT_STRING)
    updated = bytearray(CLIENT_STRING.read_bytes())
    changed = 0
    for skill_id in MARKSMAN_RETIRED_SKILL_IDS:
        live_name = str(skill_id)
        retired_name = "m" + live_name[1:]
        location = locations.get(live_name)
        if location is None:
            continue
        if retired_name in locations:
            raise RuntimeError(f"retired client string name already exists: {retired_name}")
        offset, length, encoding, indirected = location
        if indirected:
            raise RuntimeError(f"refusing to patch shared client string name: {live_name}")
        encoded = re_encrypt_string(reader, retired_name, encoding)
        if len(encoded) != length:
            raise RuntimeError(f"client string rename changed byte length: {live_name}")
        updated[offset:offset + length] = encoded
        changed += 1
    if changed and not dry_run:
        configured_backup(CLIENT_STRING)
        engine.base.atomic_write_bytes(CLIENT_STRING, bytes(updated))
    print(f"client Marksman strings retired={changed}")


def patch_buccaneer_client_strings(dry_run: bool) -> None:
    reader, locations = top_level_name_locations(CLIENT_STRING)
    updated = bytearray(CLIENT_STRING.read_bytes())
    changed = 0
    for skill_id in BUCCANEER_RETIRED_SKILL_IDS:
        live_name = str(skill_id)
        retired_name = "u" + live_name[1:]
        location = locations.get(live_name)
        if location is None:
            continue
        if retired_name in locations:
            raise RuntimeError(f"retired client string name already exists: {retired_name}")
        offset, length, encoding, indirected = location
        if indirected:
            raise RuntimeError(f"refusing to patch shared client string name: {live_name}")
        encoded = re_encrypt_string(reader, retired_name, encoding)
        if len(encoded) != length:
            raise RuntimeError(f"client string rename changed byte length: {live_name}")
        updated[offset:offset + length] = encoded
        changed += 1
    if changed and not dry_run:
        configured_backup(CLIENT_STRING)
        engine.base.atomic_write_bytes(CLIENT_STRING, bytes(updated))
    print(f"client Buccaneer strings retired={changed}")


def patch_corsair_client_strings(dry_run: bool) -> None:
    reader, locations = top_level_name_locations(CLIENT_STRING)
    updated = bytearray(CLIENT_STRING.read_bytes())
    changed = 0
    for skill_id in CORSAIR_RETIRED_SKILL_IDS:
        live_name = str(skill_id)
        retired_name = "c" + live_name[1:]
        location = locations.get(live_name)
        if location is None:
            continue
        if retired_name in locations:
            raise RuntimeError(f"retired client string name already exists: {retired_name}")
        offset, length, encoding, indirected = location
        if indirected:
            raise RuntimeError(f"refusing to patch shared client string name: {live_name}")
        encoded = re_encrypt_string(reader, retired_name, encoding)
        if len(encoded) != length:
            raise RuntimeError(f"client string rename changed byte length: {live_name}")
        updated[offset:offset + length] = encoded
        changed += 1
    if changed and not dry_run:
        configured_backup(CLIENT_STRING)
        engine.base.atomic_write_bytes(CLIENT_STRING, bytes(updated))
    print(f"client Corsair strings retired={changed}")


def patch_shadower_client_strings(strings, dry_run: bool) -> None:
    # The original migration already allocated fixed records for 4221009-1040.
    # Reuse those spans so String/Skill.img keeps its size, order and all
    # unrelated bytes while the obsolete Shadower entries disappear.
    from patch_shadower_dual_blade_skin import (
        encode_padded_record,
        locate_root_records,
    )

    original = CLIENT_STRING.read_bytes()
    image = engine.WzImage.from_bytes(
        original, key=engine.WzKey.for_region("GMS"), name=CLIENT_STRING.name
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"cannot patch malformed {CLIENT_STRING}: {image.parse_warnings}"
        )
    _, _, names, spans = locate_root_records(image, original, CLIENT_STRING)
    raw = {name: original[start:end] for name, (start, end) in zip(names, spans)}
    replacements = {}
    for spec in CURRENT_JOB.skills:
        node = root.get(str(spec.target_id))
        if not isinstance(node, engine.WzSubProperty):
            raise RuntimeError(f"missing Shadower client string: {spec.target_id}")
        source = engine.source_string_values(strings, spec.source_id)
        engine.set_string(node, "name", spec.name)
        engine.set_string(node, "desc", "TMS双刀五/六转技能。")
        compact_level_text = (
            f"伤害{spec.damage}%，攻击{spec.attack_count}次，"
            f"目标{spec.mob_count}名。"
        )
        for level in range(1, MASTER_LEVEL + 1):
            engine.set_string(node, f"h{level}", compact_level_text)
        replacements[str(spec.target_id)] = encode_padded_record(
            node, image, len(raw[str(spec.target_id)]), "name"
        )
    for skill_id in SHADOWER_DUAL_BLADE_RETIRED_SKILL_IDS:
        node = root.get(str(skill_id))
        if not isinstance(node, engine.WzSubProperty):
            continue
        engine.set_string(node, "name", "(隐藏) 已退役")
        engine.set_string(node, "desc", "已退役。")
        for level in range(1, MASTER_LEVEL + 1):
            if node.get(f"h{level}") is not None:
                engine.set_string(node, f"h{level}", "已退役。")
        replacements[str(skill_id)] = encode_padded_record(
            node, image, len(raw[str(skill_id)]), "name"
        )
    rebuilt = b"".join(replacements.get(name, raw[name]) for name in names)
    records_start, records_end = spans[0][0], spans[-1][1]
    updated = original[:records_start] + rebuilt + original[records_end:]
    if len(updated) != len(original):
        raise RuntimeError("Shadower String/Skill.img spans shifted")
    for name, record in raw.items():
        if name not in replacements and record not in updated:
            raise RuntimeError(f"unapproved client string changed: {name}")
    if not dry_run:
        configured_backup(CLIENT_STRING)
        engine.base.atomic_write_bytes(CLIENT_STRING, updated)
    print(
        f"client Shadower strings changed={len(CURRENT_JOB.skills)} "
        f"retired={len(SHADOWER_DUAL_BLADE_RETIRED_SKILL_IDS)}"
    )


def patch_bowmaster_server_strings(dry_run: bool) -> None:
    text = SERVER_STRING.read_text(encoding="utf-8")
    updated = remove_server_skill_blocks(text, BOWMASTER_RETIRED_SKILL_IDS)
    if updated != text and not dry_run:
        configured_backup(SERVER_STRING)
        engine.base.atomic_write_text(SERVER_STRING, updated)


def patch_marksman_server_strings(dry_run: bool) -> None:
    text = SERVER_STRING.read_text(encoding="utf-8")
    updated = remove_server_skill_blocks(text, MARKSMAN_RETIRED_SKILL_IDS)
    if updated != text and not dry_run:
        configured_backup(SERVER_STRING)
        engine.base.atomic_write_text(SERVER_STRING, updated)


def patch_buccaneer_server_strings(dry_run: bool) -> None:
    text = SERVER_STRING.read_text(encoding="utf-8")
    updated = remove_server_skill_blocks(text, BUCCANEER_RETIRED_SKILL_IDS)
    if updated != text and not dry_run:
        configured_backup(SERVER_STRING)
        engine.base.atomic_write_text(SERVER_STRING, updated)


def patch_corsair_server_strings(dry_run: bool) -> None:
    text = SERVER_STRING.read_text(encoding="utf-8")
    updated = remove_server_skill_blocks(text, CORSAIR_RETIRED_SKILL_IDS)
    if updated != text and not dry_run:
        configured_backup(SERVER_STRING)
        engine.base.atomic_write_text(SERVER_STRING, updated)


def patch_shadower_server_strings(strings, dry_run: bool) -> None:
    text = SERVER_STRING.read_text(encoding="utf-8")
    managed = (
        *SHADOWER_DUAL_BLADE_MANAGED_SKILL_IDS,
        *SHADOWER_DUAL_BLADE_RETIRED_SKILL_IDS,
    )
    updated = remove_server_skill_blocks(text, managed)
    closing = updated.rfind("</imgdir>")
    if closing < 0:
        raise RuntimeError("missing server String.wz root closing imgdir")
    blocks = "\n".join(
        engine.server_string_block(
            spec, engine.source_string_values(strings, spec.source_id)
        )
        for spec in CURRENT_JOB.skills
    )
    updated = updated[:closing] + blocks + "\n" + updated[closing:]
    if not dry_run:
        configured_backup(SERVER_STRING)
        engine.base.atomic_write_text(SERVER_STRING, updated)


def replace_generated_branch(target, generated, name: str) -> None:
    source = generated.child(name)
    if source is None:
        raise RuntimeError(f"generated Bishop skill is missing {target.name}/{name}")
    target._children.pop(name, None)
    target.add(engine.base.clone_property(source, name, target))


def merge_heavens_door_special(generated, key) -> None:
    foreground = generated.child("special")
    background = generated.child("special0")
    if not isinstance(foreground, engine.WzSubProperty) \
            or not isinstance(background, engine.WzSubProperty):
        raise RuntimeError("Heaven's Door requires special and special0")
    foreground = foreground.child("0")
    background = background.child("0")
    if not isinstance(foreground, engine.WzSubProperty) \
            or not isinstance(background, engine.WzSubProperty):
        raise RuntimeError("Heaven's Door special variants are missing")

    def expand(node):
        result = []
        for frame in engine.base.numeric_canvases(node):
            delay = engine.base.frame_delay(frame)
            if delay <= 0 or delay % 60 != 0:
                raise RuntimeError(f"unexpected Heaven's Door frame delay: {delay}")
            result.extend([frame] * (delay // 60))
        return result

    foreground_frames = expand(foreground)
    background_frames = expand(background)
    if len(foreground_frames) != 30 or len(background_frames) != 30:
        raise RuntimeError(
            "unexpected Heaven's Door special timeline: "
            f"{len(foreground_frames)}/{len(background_frames)}"
        )

    merged = engine.WzSubProperty("special", generated)
    for index, (background_frame, foreground_frame) in enumerate(zip(
            background_frames, foreground_frames
    )):
        canvases = (background_frame, foreground_frame)
        images = [
            engine.base.clean_rgba(engine.base.decode_source_canvas(canvas))
            for canvas in canvases
        ]
        origins = [engine.base.canvas_origin(canvas) for canvas in canvases]
        left = min(-origin[0] for origin in origins)
        top = min(-origin[1] for origin in origins)
        right = max(
            image.width - origin[0] for image, origin in zip(images, origins)
        )
        bottom = max(
            image.height - origin[1] for image, origin in zip(images, origins)
        )
        composite = Image.new(
            "RGBA", (max(1, right - left), max(1, bottom - top)), (0, 0, 0, 0)
        )
        for image, origin in zip(images, origins):
            composite.alpha_composite(image, (-origin[0] - left, -origin[1] - top))
            image.close()
        width, height, scale = engine.base.fit_size(composite.width, composite.height)
        if (width, height) != composite.size:
            resized = composite.resize((width, height), Image.Resampling.LANCZOS)
            composite.close()
            composite = resized
        frame = engine.WzCanvasProperty(str(index), merged)
        frame.width = width
        frame.height = height
        frame.format = engine.base.CANVAS_FORMAT
        frame.format2 = 0
        frame._png_data = engine.base.encode_canvas_payload(
            composite,
            engine.base.CANVAS_FORMAT,
            width,
            height,
            key=key,
            listwz=False,
            zlib_level=9,
        )
        composite.close()
        frame._png_length = len(frame._png_data)
        engine.set_vector(frame, "origin", (round(-left * scale), round(-top * scale)))
        engine.set_int(frame, "delay", 60)
        merged.add(frame)

    generated._children.pop("special", None)
    generated._children.pop("special0", None)
    generated.add(merged)


def apply_bishop_level_compatibility(target, spec: engine.SkillSpec) -> None:
    levels = target.child("level")
    if not isinstance(levels, engine.WzSubProperty):
        raise RuntimeError(f"missing Bishop level node: {spec.target_id}")
    for level in levels.children():
        if spec.target_id == 2321020:
            engine.set_int(level, "damage", spec.damage)
            engine.set_int(level, "mad", spec.damage * spec.attack_count)
            engine.set_int(level, "attackCount", 1)
            engine.set_int(level, "mobCount", spec.mob_count)
            engine.set_int(level, "mpCon", spec.mp_con)
            engine.set_int(level, "cooltime", spec.cooldown)
            engine.set_vector(level, "lt", spec.lt)
            engine.set_vector(level, "rb", spec.rb)
            if spec.duration_seconds is not None:
                engine.set_int(level, "time", spec.duration_seconds)
        elif spec.target_id == 2321024:
            engine.set_int(level, "cooltime", spec.cooldown)
        elif spec.target_id == 2321032:
            engine.set_int(level, "x", -44)
            engine.set_int(level, "prop", 100)


def patch_bishop_client_skill(groups, metadata, dry_run: bool) -> None:
    if CURRENT_JOB is None or CURRENT_JOB.config.key != "bishop":
        raise RuntimeError("Bishop client patch called for another job")
    path = engine.CLIENT_SKILL
    original = path.read_bytes()
    image = engine.WzImage.from_bytes(
        original, key=engine.WzKey.for_region("GMS"), name=path.name
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"cannot patch malformed {path}: {image.parse_warnings}")
    skill_root = root.get("skill")
    if not isinstance(skill_root, engine.WzSubProperty):
        raise RuntimeError("client 232.img has no skill root")
    (size_offset, old_block_size, count_offset, count_end,
     names, spans) = locate_client_skill_records(image, path)
    raw_records = {
        name: original[start:end]
        for name, (start, end) in zip(names, spans)
    }
    specs = {spec.target_id: spec for spec in CURRENT_JOB.skills}
    replacements = {}
    key = image.wz_file.reader.key
    for skill_id, branches in BISHOP_CLIENT_REPLACEMENTS.items():
        target = skill_root.child(str(skill_id))
        if not isinstance(target, engine.WzSubProperty):
            raise RuntimeError(f"missing existing Bishop skill: {skill_id}")
        generated = build_skill(specs[skill_id], skill_root, key, groups, metadata)
        if skill_id == 2321035:
            merge_heavens_door_special(generated, key)
            target._children.pop("effect0", None)
            target._children.pop("special0", None)
        for branch in branches:
            replace_generated_branch(target, generated, branch)
        apply_bishop_level_compatibility(target, specs[skill_id])
        encoded = _encode_property_list((target,), image.wz_file.reader)
        count_prefix = encode_compressed_int(1)
        if not encoded.startswith(count_prefix):
            raise RuntimeError("unexpected Bishop property record prefix")
        replacements[str(skill_id)] = encoded[len(count_prefix):]
        print(f"client skill record: {skill_id}")
    additions = []
    for skill_id in BISHOP_CLIENT_ADDITIONS:
        generated = build_skill(specs[skill_id], skill_root, key, groups, metadata)
        encoded = _encode_property_list((generated,), image.wz_file.reader)
        count_prefix = encode_compressed_int(1)
        if not encoded.startswith(count_prefix):
            raise RuntimeError("unexpected Bishop property record prefix")
        record = encoded[len(count_prefix):]
        if str(skill_id) in raw_records:
            replacements[str(skill_id)] = record
        else:
            additions.append(record)
        print(f"client hidden skill record: {skill_id}")
    rebuilt_records = (
        b"".join(replacements.get(name, raw_records[name]) for name in names)
        + b"".join(additions)
    )
    records_start, records_end = spans[0][0], spans[-1][1]
    updated = bytearray(original[:records_start] + rebuilt_records + original[records_end:])
    new_count = encode_compressed_int(len(names) + len(additions))
    if len(new_count) != count_end - count_offset:
        raise RuntimeError("Bishop skill count encoding size changed")
    updated[count_offset:count_end] = new_count
    new_block_size = old_block_size + len(updated) - len(original)
    updated[size_offset:size_offset + 4] = struct.pack("<I", new_block_size)
    for name in names:
        if name not in replacements and raw_records[name] not in updated:
            raise RuntimeError(f"unchanged Bishop record was not preserved: {name}")
    if not dry_run:
        configured_backup(path)
        engine.base.atomic_write_bytes(path, bytes(updated))
    print(f"client Bishop records changed={len(replacements)} preserved={len(names) - len(replacements)}")


def configure(job: RuntimeJob) -> None:
    global CURRENT_JOB
    CURRENT_JOB = job
    config = job.config
    engine.TMS_ROOT = TMS_ROOT
    engine.MS_EXPORT_ROOT = MS_EXPORT_ROOT
    engine.SOURCE_PATHS = {
        group: TMS_ROOT / "Skill" / "_Canvas" / f"{group}.img"
        for group in sorted(referenced_canvas_groups(job))
    }
    engine.CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / f"{config.book}.img"
    engine.CLIENT_STRING = CLIENT_STRING
    engine.CLIENT_MAP_EFFECT = ROOT / "clien" / "Data" / "Map" / "Effect.img"
    engine.SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / f"{config.book}.img.xml"
    engine.SERVER_STRING = SERVER_STRING
    engine.FIELD_EFFECT_ROOT = f"customSkill/{config.key}"
    video_markers = [
        f"video{spec.target_id}" for spec in job.skills
        if not spec.hidden and "<video " in (
            MS_EXPORT_ROOT / f"{spec.source_id}.xml"
        ).read_text(encoding="utf-8")
    ]
    if config.key == "shadower":
        # The two Dual Blade origin skills contain modern screen videos. The
        # legacy client receives them through the existing MCV marker path.
        video_markers = [
            f"video{spec.target_id}" for spec in job.skills
            if not spec.hidden and spec.source_id in {4361500, 4361504}
        ]
    if config.key == "buccaneer":
        video_markers.append(BUCCANEER_HOWLING_FIST_VIDEO_MARKER)
    elif config.key == "corsair":
        video_markers.append(CORSAIR_DEATH_EYE_VIDEO_MARKER)
    engine.VIDEO_MARKERS = tuple(video_markers)
    engine.MASTER_LEVEL = MASTER_LEVEL
    engine.CUSTOM_SKILL_IDS = (
        range(config.target_start, 4221041)
        if config.key == "shadower"
        else range(config.target_start, max(spec.target_id for spec in job.skills) + 1)
    )
    engine.SKILLS = job.skills
    engine.TIMED_EFFECTS = (
        {2321024: engine.TimedEffectSpec(
            ("prepare",), ("keydown",), ("keydownend",), 5000
        )}
        if config.key == "bishop" else {}
    )
    engine.base.SKILLS = job.skills
    engine.base.MS_EXPORT_ROOT = MS_EXPORT_ROOT
    engine.backup = configured_backup
    engine.source_node = source_node
    engine.tracks = source_tracks if config.key == "buccaneer" else ORIGINAL_TRACKS
    engine.build_skill = build_skill
    engine.server_skill_block = server_skill_block


def validate_job() -> None:
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    image = engine.WzImage.from_bytes(
        engine.CLIENT_SKILL.read_bytes(), key=engine.WzKey.for_region("GMS"),
        name=engine.CLIENT_SKILL.name,
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"invalid client IMG: {image.parse_warnings}")
    canvas_count = 0
    for spec in CURRENT_JOB.skills:
        node = root.get(f"skill/{spec.target_id}")
        if not isinstance(node, engine.WzSubProperty):
            raise RuntimeError(f"missing client skill: {spec.target_id}")
        level = node.get("level/30")
        if level is None:
            raise RuntimeError(f"missing level 30: {spec.target_id}")
        if CURRENT_JOB.config.key in {"shadower", "nightLord"}:
            for name in ("weapon", "weapon2", "subWeapon"):
                if node.get(name) is not None:
                    raise RuntimeError(
                        f"{CURRENT_JOB.config.key} V/VI weapon restriction remains: "
                        f"{spec.target_id}/{name}"
                    )
        values = (
            int(level.get("damage").value), int(level.get("attackCount").value),
            int(level.get("mobCount").value), int(level.get("mpCon").value),
            int(level.get("cooltime").value),
        )
        expected_attack_count = 1 if spec.target_id == 2321020 else spec.attack_count
        expected = (
            spec.damage, expected_attack_count, spec.mob_count,
            spec.mp_con, spec.cooldown,
        )
        if values != expected:
            raise RuntimeError(f"parameter mismatch {spec.target_id}: {values} != {expected}")
        if spec.target_id == 2321020:
            mad = int(level.get("mad").value)
            if mad != spec.damage * spec.attack_count:
                raise RuntimeError(f"invalid legacy summon damage {spec.target_id}: {mad}")
        if spec.include_hit and not engine.base.numeric_canvases(node.get("hit/0")):
            raise RuntimeError(f"missing monster hit effect: {spec.target_id}")
        stack = [node]
        while stack:
            current = stack.pop()
            if isinstance(current, engine.WzCanvasProperty):
                canvas_count += 1
                if int(current.format) != 1 or int(current.format2) != 0:
                    raise RuntimeError(f"non-ARGB4444 Canvas: {spec.target_id}")
            if hasattr(current, "children"):
                stack.extend(current.children())
    if CURRENT_JOB.config.key == "bishop":
        for source_id, (_, _, attack_type, attack_after, mob_count) in BISHOP_SUMMON_INFO.items():
            spec = next(spec for spec in CURRENT_JOB.skills if spec.source_id == source_id)
            info = root.get(f"skill/{spec.target_id}/summon/attack1/info")
            if not isinstance(info, engine.WzSubProperty):
                raise RuntimeError(f"missing legacy summon attack info: {spec.target_id}")
            actual = (
                int(info.get("type").value), int(info.get("attackAfter").value),
                int(info.get("mobCount").value),
            )
            if actual != (attack_type, attack_after, mob_count):
                raise RuntimeError(f"invalid legacy summon attack info {spec.target_id}: {actual}")
    elif CURRENT_JOB.config.key == "buccaneer":
        for property_name, expected in BUCCANEER_SERPENT_ASSAULT_HIT_METADATA.items():
            value = root.get(
                f"skill/{BUCCANEER_SERPENT_ASSAULT_ID}/hit/0/{property_name}"
            )
            if value is None or int(value.value) != expected:
                raise RuntimeError(
                    f"Serpent Assault VI hit metadata mismatch: {property_name}"
                )
    server = ET.parse(engine.SERVER_SKILL).getroot()
    server_skills = server.find("./imgdir[@name='skill']")
    for spec in CURRENT_JOB.skills:
        if server_skills.find(f"./imgdir[@name='{spec.target_id}']") is None:
            raise RuntimeError(f"missing server skill: {spec.target_id}")
    if CURRENT_JOB.config.key == "bowmaster":
        client_strings = engine.WzImage.from_bytes(
            CLIENT_STRING.read_bytes(), key=engine.WzKey.for_region("GMS"),
            name=CLIENT_STRING.name,
        ).parse()
        server_strings = ET.parse(SERVER_STRING).getroot()
        for skill_id in BOWMASTER_RETIRED_SKILL_IDS:
            if root.get(f"skill/{skill_id}") is not None:
                raise RuntimeError(f"retired client skill still exists: {skill_id}")
            if client_strings.get(str(skill_id)) is not None:
                raise RuntimeError(f"retired client string still exists: {skill_id}")
            if server_skills.find(f"./imgdir[@name='{skill_id}']") is not None:
                raise RuntimeError(f"retired server skill still exists: {skill_id}")
            if server_strings.find(f"./imgdir[@name='{skill_id}']") is not None:
                raise RuntimeError(f"retired server string still exists: {skill_id}")
    elif CURRENT_JOB.config.key == "nightLord":
        client_strings = engine.WzImage.from_bytes(
            CLIENT_STRING.read_bytes(), key=engine.WzKey.for_region("GMS"),
            name=CLIENT_STRING.name,
        ).parse()
        server_strings = ET.parse(SERVER_STRING).getroot()
        for skill_id in NIGHT_LORD_RETIRED_SKILL_IDS:
            if root.get(f"skill/{skill_id}") is not None:
                raise RuntimeError(f"retired Night Lord client skill remains: {skill_id}")
            if client_strings.get(str(skill_id)) is not None:
                raise RuntimeError(f"retired Night Lord client string remains: {skill_id}")
            if server_skills.find(f"./imgdir[@name='{skill_id}']") is not None:
                raise RuntimeError(f"retired Night Lord server skill remains: {skill_id}")
            if server_strings.find(f"./imgdir[@name='{skill_id}']") is not None:
                raise RuntimeError(f"retired Night Lord server string remains: {skill_id}")
    elif CURRENT_JOB.config.key == "shadower":
        client_strings = engine.WzImage.from_bytes(
            CLIENT_STRING.read_bytes(), key=engine.WzKey.for_region("GMS"),
            name=CLIENT_STRING.name,
        ).parse()
        server_strings = ET.parse(SERVER_STRING).getroot()
        for skill_id in SHADOWER_DUAL_BLADE_RETIRED_SKILL_IDS:
            if root.get(f"skill/{skill_id}") is not None:
                raise RuntimeError(f"retired Shadower client skill remains: {skill_id}")
            retired_name = client_strings.get(f"{skill_id}/name")
            if retired_name is None or "已退役" not in str(retired_name.value):
                raise RuntimeError(f"retired Shadower client string is visible: {skill_id}")
            if server_skills.find(f"./imgdir[@name='{skill_id}']") is not None:
                raise RuntimeError(f"retired Shadower server skill remains: {skill_id}")
            if server_strings.find(f"./imgdir[@name='{skill_id}']") is not None:
                raise RuntimeError(f"retired Shadower server string remains: {skill_id}")
    elif CURRENT_JOB.config.key == "marksman":
        client_strings = engine.WzImage.from_bytes(
            CLIENT_STRING.read_bytes(), key=engine.WzKey.for_region("GMS"),
            name=CLIENT_STRING.name,
        ).parse()
        server_strings = ET.parse(SERVER_STRING).getroot()
        for skill_id in MARKSMAN_RETIRED_SKILL_IDS:
            if root.get(f"skill/{skill_id}") is not None:
                raise RuntimeError(f"retired client skill still exists: {skill_id}")
            if client_strings.get(str(skill_id)) is not None:
                raise RuntimeError(f"retired client string still exists: {skill_id}")
            if server_skills.find(f"./imgdir[@name='{skill_id}']") is not None:
                raise RuntimeError(f"retired server skill still exists: {skill_id}")
            if server_strings.find(f"./imgdir[@name='{skill_id}']") is not None:
                raise RuntimeError(f"retired server string still exists: {skill_id}")
        marker = engine.base.numeric_canvases(root.get("skill/3221009/hit/0"))
        impacts = engine.base.numeric_canvases(root.get("skill/3221010/hit/0"))
        if len(marker) != 7 or len(impacts) != 6:
            raise RuntimeError(
                f"invalid True Sniping marker/impact timeline: {len(marker)}/{len(impacts)}"
            )
        if root.get("skill/3221009/special") is not None:
            raise RuntimeError("True Sniping target marker remained on unsupported special")
    elif CURRENT_JOB.config.key == "corsair":
        client_strings = engine.WzImage.from_bytes(
            CLIENT_STRING.read_bytes(), key=engine.WzKey.for_region("GMS"),
            name=CLIENT_STRING.name,
        ).parse()
        server_strings = ET.parse(SERVER_STRING).getroot()
        for skill_id in CORSAIR_RETIRED_SKILL_IDS:
            if root.get(f"skill/{skill_id}") is not None:
                raise RuntimeError(f"retired client skill still exists: {skill_id}")
            if client_strings.get(str(skill_id)) is not None:
                raise RuntimeError(f"retired client string still exists: {skill_id}")
            if server_skills.find(f"./imgdir[@name='{skill_id}']") is not None:
                raise RuntimeError(f"retired server skill still exists: {skill_id}")
            if server_strings.find(f"./imgdir[@name='{skill_id}']") is not None:
                raise RuntimeError(f"retired server string still exists: {skill_id}")
    active = [spec.target_id for spec in CURRENT_JOB.skills if not spec.hidden]
    print(f"validated {CURRENT_JOB.config.key}: skills={len(CURRENT_JOB.skills)} "
          f"active={len(active)} canvases={canvas_count}")


def migrate_job(job: RuntimeJob, dry_run: bool) -> None:
    configure(job)
    if job.config.key == "nightLord":
        import retire_night_lord_rapid_throw as retirement
        retirement.retire(dry_run=dry_run)
        groups, _, metadata = engine.load_sources()
        patch_night_lord_client_skill(groups, metadata, dry_run)
        patch_server_skill(dry_run)
        if not dry_run:
            validate_job()
        return
    if job.config.key == "shadower":
        restore_shadower_lower_job_contract(dry_run)
        groups, strings, metadata = engine.load_sources()
        patch_shadower_client_skill(groups, metadata, dry_run)
        patch_shadower_client_strings(strings, dry_run)
        patch_server_skill(dry_run)
        patch_shadower_server_strings(strings, dry_run)
        for spec in job.skills:
            if not spec.hidden and spec.source_id in {4361500, 4361504}:
                patch_incremental_map_effect(
                    "customSkill/shadower", f"video{spec.target_id}", dry_run
                )
        if not dry_run:
            validate_job()
        return
    if job.config.key == "bowmaster":
        groups, _, metadata = engine.load_sources()
        patch_bowmaster_client_skill(groups, metadata, dry_run)
        patch_bowmaster_client_strings(dry_run)
        patch_server_skill(dry_run)
        patch_bowmaster_server_strings(dry_run)
        if not dry_run:
            validate_job()
        return
    if job.config.key == "marksman":
        groups, _, metadata = engine.load_sources()
        patch_marksman_client_skill(groups, metadata, dry_run)
        patch_marksman_client_strings(dry_run)
        patch_server_skill(dry_run)
        patch_marksman_server_strings(dry_run)
        if not dry_run:
            validate_job()
        return
    if job.config.key == "buccaneer":
        groups, _, metadata = engine.load_sources()
        patch_buccaneer_client_skill(groups, metadata, dry_run)
        patch_buccaneer_map_effect(dry_run)
        patch_buccaneer_client_strings(dry_run)
        patch_server_skill(dry_run)
        patch_buccaneer_server_strings(dry_run)
        if not dry_run:
            validate_job()
        return
    if job.config.key == "corsair":
        patch_corsair_client_skill(dry_run)
        patch_corsair_map_effect(dry_run)
        patch_corsair_client_strings(dry_run)
        patch_server_skill(dry_run)
        patch_corsair_server_strings(dry_run)
        if not dry_run:
            validate_job()
        return
    groups, strings, metadata = engine.load_sources()
    if job.config.key == "bishop":
        patch_bishop_client_skill(groups, metadata, dry_run)
    else:
        engine.patch_client_skill(groups, metadata, dry_run)
        engine.patch_client_string(strings, dry_run)
    patch_server_skill(dry_run)
    if job.config.key != "bishop":
        engine.patch_server_string(strings, dry_run)
    if not dry_run:
        validate_job()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", choices=("all", *(job.key for job in JOBS)), default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    jobs = build_runtime_jobs()
    selected = jobs if args.job == "all" else tuple(
        job for job in jobs if job.config.key == args.job
    )
    for job in selected:
        configure(job)
        if args.validate_only:
            validate_job()
        else:
            migrate_job(job, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

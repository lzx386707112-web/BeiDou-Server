#!/usr/bin/env python3
"""Migrate attack-only TMS V/VI skills for the remaining supported Explorers."""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
sys.path.insert(0, str(PATCH_SKILL))

import patch_blaze_wizard_v_vi as engine  # noqa: E402


TMS_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
MS_EXPORT_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-MS-Export/ExplorerOther")
STRING_JSON = TMS_ROOT / "String" / "Skill.img.json"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"
MASTER_LEVEL = 30


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
    JobConfig("shadower", 422, "424", "40004",
              (400041002, 400041003, 400041004, 400041005,
               400041025, 400041026, 400041027, 400041039,
               400041069, 400041070, 400041071, 400041072, 400041073),
              frozenset({400041002, 400041025, 400041039, 400041069}),
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
    400021030: 400021031,
    400031055: 400031056,
    400041025: 400041026,
}
PARAMETER_FIELDS = {
    400031002: {"damage": "q", "attackCount": "y", "mobCount": "z"},
}
# Modern Skill.wz reuses `time` for damage, animation milliseconds, projectile
# lifetime, and actual duration. The legacy server interprets level/time only as
# seconds, so overloaded fields need explicit semantic conversion.
DURATION_OVERRIDES = {
    400021094: 40,
    2241002: 4,
    400031021: None,
    3141004: 60,
    3241000: None,
    3241001: None,
    3241003: None,
    5141000: 10,
    5141002: None,
    400051021: None,
    400051040: None,
}
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
ORIGINAL_BUILD_SKILL = engine.build_skill


def expression_value(value: str | None, default: int = 0) -> int:
    if value is None:
        return default
    value = re.sub(r"(?<=\d)(?=(?:d|u|log(?:10|20|30))\()", "*", value)
    return int(eval(value, {"__builtins__": {}}, {
        "x": MASTER_LEVEL,
        "d": math.floor,
        "u": math.ceil,
        "min": min,
        "max": max,
        "log10": lambda level: int(level >= 10),
        "log20": lambda level: int(level >= 20),
        "log30": lambda level: int(level >= 30),
    }))


def named_child(node: ET.Element | None, name: str) -> ET.Element | None:
    if node is None:
        return None
    return next((child for child in node if child.get("name") == name), None)


def scalar(node: ET.Element | None, name: str, default: int = 0) -> int:
    child = named_child(node, name)
    return expression_value(None if child is None else child.get("value"), default)


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
    damage = scalar(parameter_common, fields.get("damage", "damage"))
    if damage <= 0 and not active:
        return None
    if damage <= 0:
        raise RuntimeError(f"active attack has no damage parameter: {source_id}")
    attack_count = max(1, scalar(parameter_common, fields.get("attackCount", "attackCount"), 1))
    mob_count = max(1, scalar(parameter_common, fields.get("mobCount", "mobCount"), 1))
    top_names = {child.get("name") for child in root}
    if "keydown" in top_names:
        effects = tuple(name for name in ("keydown", "keydown0") if name in top_names)
    else:
        effects = tuple(name for name in EFFECT_CANDIDATES if name in top_names)[:2]
    extras = tuple(name for name in EXTRA_CANDIDATES if name in top_names and name not in effects)
    projectiles = tuple(name for name in PROJECTILE_CANDIDATES if name in top_names)
    duration = (DURATION_OVERRIDES[source_id]
                if source_id in DURATION_OVERRIDES else scalar(own_common, "time"))
    return engine.SkillSpec(
        target_id=target_id,
        source_id=source_id,
        source_group=root.get("sourceGroup"),
        name=names.get(source_id, str(source_id)),
        damage=damage,
        attack_count=min(15, attack_count),
        mob_count=min(15, mob_count),
        mp_con=scalar(own_common, "mpCon"),
        cooldown=scalar(own_common, "cooltime"),
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


def build_runtime_jobs() -> tuple[RuntimeJob, ...]:
    roots = exported_roots()
    names = source_names()
    jobs = []
    for config in JOBS:
        source_ids = [*config.v_ids, *vi_ids(config, roots)]
        specs = []
        target_id = config.target_start
        for source_id in source_ids:
            root = roots.get(source_id)
            if root is None:
                raise RuntimeError(f"source {source_id} was not exported")
            invisible = named_child(root, "invisible") is not None
            active = source_id in config.active_v_ids or (
                root.get("sourceGroup") == config.vi_group and not invisible
            )
            spec = make_spec(config, source_id, target_id, active, roots, names)
            if spec is not None:
                specs.append(spec)
                target_id += 1
        source_by_target = {spec.target_id: spec.source_id for spec in specs}
        target_by_source = {spec.source_id: spec.target_id for spec in specs}
        jobs.append(RuntimeJob(config, tuple(specs), source_by_target, target_by_source))
    return tuple(jobs)


def multi_attack_schedule(job: RuntimeJob, spec: engine.SkillSpec) -> dict[int, tuple[int, ...]]:
    root = ET.parse(MS_EXPORT_ROOT / f"{spec.source_id}.xml").getroot()
    timeline = named_child(root, "multiAttackInfo")
    if timeline is None:
        return {}
    elapsed = 0
    grouped: dict[int, list[int]] = {}
    for phase in timeline:
        elapsed += scalar(phase, "attackTime")
        source_id = scalar(phase, "x", spec.source_id)
        replay_id = job.target_by_source.get(source_id, spec.target_id)
        grouped.setdefault(replay_id, []).append(elapsed)
    return {skill_id: tuple(times) for skill_id, times in grouped.items()}


def configured_backup(path: Path) -> None:
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    target = path.with_name(path.name + f".bak-{CURRENT_JOB.config.key}-v-vi")
    if not target.exists():
        shutil.copy2(path, target)
        print(f"backup: {target}")


def referenced_canvas_groups(job: RuntimeJob) -> set[str]:
    groups = {job.config.vi_group, job.config.v_group}
    for source_id in job.source_by_target.values():
        text = (MS_EXPORT_ROOT / f"{source_id}.xml").read_text(encoding="utf-8")
        groups.update(re.findall(r"Skill/_Canvas/(\d+)\.img/", text))
    return groups


def build_skill(spec, parent, key, groups, metadata):
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    target = ORIGINAL_BUILD_SKILL(spec, parent, key, groups, metadata)
    engine.set_string(target.child("action"), "0", CURRENT_JOB.config.action)
    if CURRENT_JOB.config.elem_attr is None:
        target._children.pop("elemAttr", None)
    else:
        engine.set_string(target, "elemAttr", CURRENT_JOB.config.elem_attr)
    return target


def source_node(groups, skill_id: int):
    for group in groups.values():
        node = group.get(f"skill/{skill_id}")
        if isinstance(node, engine.WzSubProperty):
            return node
    raise RuntimeError(f"missing source skill/{skill_id}")


def server_skill_block(spec: engine.SkillSpec) -> str:
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    lines = [f'  <imgdir name="{spec.target_id}">', '    <imgdir name="action">',
             f'      <string name="0" value="{CURRENT_JOB.config.action}"/>', "    </imgdir>",
             '    <imgdir name="level">']
    for level in range(1, MASTER_LEVEL + 1):
        lines.extend([
            f'      <imgdir name="{level}">',
            f'        <int name="attackCount" value="{spec.attack_count}"/>',
            f'        <int name="cooltime" value="{spec.cooldown}"/>',
            f'        <int name="damage" value="{spec.damage}"/>',
            *([f'        <int name="mad" value="{spec.damage}"/>'] if CURRENT_JOB.config.magic else []),
            f'        <string name="hs" value="h{level}"/>',
            f'        <vector name="lt" x="{spec.lt[0]}" y="{spec.lt[1]}"/>',
            f'        <int name="mobCount" value="{spec.mob_count}"/>',
            f'        <int name="mpCon" value="{spec.mp_con}"/>',
            f'        <vector name="rb" x="{spec.rb[0]}" y="{spec.rb[1]}"/>',
            *([f'        <int name="time" value="{spec.duration_seconds}"/>']
              if spec.duration_seconds is not None else []),
            "      </imgdir>",
        ])
    lines.extend(["    </imgdir>", f'    <int name="masterLevel" value="{MASTER_LEVEL}"/>'])
    if CURRENT_JOB.config.elem_attr is not None:
        lines.append(f'    <string name="elemAttr" value="{CURRENT_JOB.config.elem_attr}"/>')
    if spec.hidden:
        lines.append('    <int name="invisible" value="1"/>')
    lines.append("  </imgdir>")
    return "\n".join(lines)


def patch_server_skill(dry_run: bool) -> None:
    if CURRENT_JOB is None:
        raise RuntimeError("job is not configured")
    path = engine.SERVER_SKILL
    text = path.read_text(encoding="utf-8")
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
    engine.VIDEO_MARKERS = tuple(
        f"video{spec.target_id}" for spec in job.skills
        if not spec.hidden and "<video " in (
            MS_EXPORT_ROOT / f"{spec.source_id}.xml"
        ).read_text(encoding="utf-8")
    )
    engine.MASTER_LEVEL = MASTER_LEVEL
    engine.CUSTOM_SKILL_IDS = range(config.target_start, config.target_start + len(job.skills))
    engine.SKILLS = job.skills
    engine.TIMED_EFFECTS = {}
    engine.base.SKILLS = job.skills
    engine.base.MS_EXPORT_ROOT = MS_EXPORT_ROOT
    engine.backup = configured_backup
    engine.source_node = source_node
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
    canvas_count = 0
    for spec in CURRENT_JOB.skills:
        node = root.get(f"skill/{spec.target_id}")
        if not isinstance(node, engine.WzSubProperty):
            raise RuntimeError(f"missing client skill: {spec.target_id}")
        level = node.get("level/30")
        if level is None:
            raise RuntimeError(f"missing level 30: {spec.target_id}")
        values = (
            int(level.get("damage").value), int(level.get("attackCount").value),
            int(level.get("mobCount").value), int(level.get("mpCon").value),
            int(level.get("cooltime").value),
        )
        expected = (spec.damage, spec.attack_count, spec.mob_count, spec.mp_con, spec.cooldown)
        if values != expected:
            raise RuntimeError(f"parameter mismatch {spec.target_id}: {values} != {expected}")
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
    server = ET.parse(engine.SERVER_SKILL).getroot()
    server_skills = server.find("./imgdir[@name='skill']")
    for spec in CURRENT_JOB.skills:
        if server_skills.find(f"./imgdir[@name='{spec.target_id}']") is None:
            raise RuntimeError(f"missing server skill: {spec.target_id}")
    active = [spec.target_id for spec in CURRENT_JOB.skills if not spec.hidden]
    print(f"validated {CURRENT_JOB.config.key}: skills={len(CURRENT_JOB.skills)} "
          f"active={len(active)} canvases={canvas_count}")


def migrate_job(job: RuntimeJob, dry_run: bool) -> None:
    configure(job)
    groups, strings, metadata = engine.load_sources()
    engine.patch_client_skill(groups, metadata, dry_run)
    engine.patch_client_string(strings, dry_run)
    patch_server_skill(dry_run)
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

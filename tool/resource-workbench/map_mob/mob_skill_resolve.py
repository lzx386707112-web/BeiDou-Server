#!/usr/bin/env python3
"""Map a mob info/skill slot onto v83 MobSkill.img and TMS MobSkill/_Canvas files.

Mob IMG ``skillN`` is the boss pose. ``info/skill/*/skill`` is the MobSkill *type
id*. That id indexes:

- old client ``clien/Data/Skill/MobSkill.img`` child ``{id}/level/{level}``
- server ``gms-server/wz/Skill.wz/MobSkill.img.xml`` the same path
- TMS ``Skill/MobSkill/_Canvas/{id}.img`` (one file per type, like Mob/_Canvas)

Do not copy TMS 200+ skill files into the v83 MobSkill.img. Most Damien combat
is Java, not a new MobSkill record.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[2]
_TMS_CANVAS = _ROOT.parent / "TMS" / "MapleStory-IMG" / "Data" / "Skill" / "MobSkill" / "_Canvas"
_CLIENT_IMG = _ROOT / "clien" / "Data" / "Skill" / "MobSkill.img"
_SERVER_XML = _ROOT / "gms-server" / "wz" / "Skill.wz" / "MobSkill.img.xml"

# Java MobSkillType ids that v83 already routes. Extra TMS files (277, 800, …)
# are not this table.
MOB_SKILL_NAMES = {
    100: "ATTACK_UP", 101: "MAGIC_ATTACK_UP", 102: "DEFENSE_UP", 103: "MAGIC_DEFENSE_UP",
    105: "WEAPON_ATTACK_UP",
    110: "ATTACK_UP_M", 111: "MAGIC_ATTACK_UP_M", 112: "DEFENSE_UP_M", 113: "MAGIC_DEFENSE_UP_M",
    114: "HEAL_M", 115: "HASTE_M",
    120: "SEAL", 121: "DARKNESS", 122: "WEAKNESS", 123: "STUN", 124: "CURSE",
    125: "POISON", 126: "SLOW", 127: "DISPEL", 128: "SEDUCE", 129: "BANISH",
    131: "AREA_POISON", 132: "REVERSE_INPUT", 133: "UNDEAD", 134: "STOP_POTION",
    135: "STOP_MOTION", 136: "FEAR", 138: "CYGNUS_UNSUPPORTED",
    140: "PHYSICAL_IMMUNE", 141: "MAGIC_IMMUNE", 142: "HARD_SKIN",
    143: "PHYSICAL_COUNTER", 144: "MAGIC_COUNTER", 145: "PHYSICAL_AND_MAGIC_COUNTER",
    150: "PAD", 151: "MAD", 152: "PDR", 153: "MDR", 154: "ACC", 155: "EVA",
    156: "SPEED", 157: "SEAL_SKILL",
    170: "SUMMON_170", 174: "AKAYRUM_BLACK_HOLE_VISUAL", 176: "AKAYRUM_SCREEN_CRACK_VISUAL",
    177: "AKAYRUM_GREEN_ORB_VISUAL", 183: "WILL_WEB_BURST", 184: "MAGNUS_METEOR_STORM",
    185: "LUCID_DREAM_BURST", 186: "SUMMON_186", 187: "SEREN_SACRED_BURST",
    188: "SUMMON_188", 189: "SUMMON_189", 190: "SUMMON_190", 191: "SUMMON_191",
    200: "SUMMON", 201: "SUMMON_201", 202: "SUMMON_202", 203: "SUMMON_203",
    214: "DAMAGE_CANCEL", 215: "MOB_CHANGE",
}

# applyEffect is intercepted; changing MobSkill.img x/lt still hits other bosses.
JAVA_INTERCEPT_IDS = {176, 185, 174, 177, 183, 184, 187}
FLASH_IDS = {170}
HARD_SKIN_IDS = {142}
DISEASE_IDS = {120, 121, 122, 123, 124, 125, 126, 127, 128, 132, 133}

WHAT_IT_DOES = (
    "MobSkill 是『技能类型表』，不是 Boss 的 skill2 文件夹。"
    "客户端用它播通用 effect/affected 贴图，并读 hp 门槛、interval、time、lt/rb、x。"
    "服务端 MobSkillFactory 读同一路径，决定 MP、冷却、疾病范围、召唤列表。"
    "怪物 info/skill 的 skill/level/action 三元组：skill=类型 ID，level=表里的档，action=播 Mob 的 skill{action} 动作。"
)

WHEN_TO_EDIT = [
    "所有使用同一 ID+等级的怪都要改默认冷却、持续时间、MP、lt/rb、hp 门槛时，才改 MobSkill。",
    "info/skill 绑了一个 v83 表里不存在的 ID/等级，getMobSkill 会空，这时应改成已有 ID，或只增量插入那一个 level 块（禁止整份 MobSkill.img 重写）。",
    "旧端疾病技能的 affected/effect 贴图缺失、全服都缺，才动客户端 MobSkill.img 的 Canvas。",
]

WHEN_NOT_TO_EDIT = [
    "单个 Boss 的光球个数/轨迹、预警圈、占位怪：写 *BossCompat，不要改全局表。",
    "不要把 TMS Skill/MobSkill/_Canvas 里 200+ 的新文件合并进 v83 MobSkill.img。",
    "戴米安 176/185：Java 已拦截 applyEffect。改 176 的 x 会让赤血女王等共用档位异常。",
    "TMS 戴米安的 142 是现代 FSM，v83 的 142 是硬皮。不要靠改 142 还原光球。",
    "禁止绑 170（旧端 Flash）。",
]


def _int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


_xml_cache: dict[str, Any] = {"mtime": None, "index": None}


def server_index() -> dict[int, dict[str, Any]]:
    path = _SERVER_XML
    mtime = path.stat().st_mtime_ns if path.is_file() else None
    if _xml_cache["index"] is not None and _xml_cache["mtime"] == mtime:
        return _xml_cache["index"]
    index: dict[int, dict[str, Any]] = {}
    if path.is_file():
        root = ET.parse(path).getroot()
        for skill in root:
            name = skill.get("name") or ""
            if skill.tag != "imgdir" or not name.isdigit():
                continue
            skill_id = int(name)
            levels: dict[int, dict[str, Any]] = {}
            level_parent = next((child for child in skill if child.get("name") == "level"), None)
            if level_parent is not None:
                for level in level_parent:
                    if not (level.get("name") or "").isdigit():
                        continue
                    fields = {}
                    folders = []
                    for child in level:
                        child_name = child.get("name") or ""
                        if child.tag == "imgdir":
                            folders.append(child_name)
                        elif child.tag in {"int", "string", "float"}:
                            fields[child_name] = child.get("value")
                        elif child.tag == "vector":
                            fields[child_name] = {
                                "x": child.get("x"), "y": child.get("y"),
                            }
                    levels[int(level.get("name"))] = {"fields": fields, "folders": folders}
            index[skill_id] = {
                "levels": sorted(levels),
                "byLevel": levels,
            }
    _xml_cache["mtime"] = mtime
    _xml_cache["index"] = index
    return index


def tms_canvas_file(skill_id: int) -> Path:
    return _TMS_CANVAS / f"{skill_id}.img"


def tms_canvas_info(skill_id: int) -> dict[str, Any]:
    path = tms_canvas_file(skill_id)
    exists = path.is_file()
    return {
        "path": str(path) if exists else f"TMS/MapleStory-IMG/Data/Skill/MobSkill/_Canvas/{skill_id}.img",
        "exists": exists,
        "size": path.stat().st_size if exists else 0,
        "note": "TMS 每个技能类型一个 IMG，只存该 ID 的像素/现代节点；逻辑等级仍在 JSON/完整记录里。",
    }


def advice_for(
    skill_id: int | None,
    level: int | None,
    *,
    tms_skill_id: int | None = None,
    intercept: bool = False,
) -> dict[str, Any]:
    if skill_id is None:
        return {
            "edit": False,
            "verdict": "skip",
            "reason": "当前节点没有 info/skill 绑定，改 MobSkill.img 不会让这个动作飞出光球。",
        }
    index = server_index()
    record = index.get(skill_id)
    has_level = bool(record and level in record["levels"]) if level is not None else bool(record)
    if skill_id in FLASH_IDS:
        return {
            "edit": False,
            "verdict": "forbidden",
            "reason": "MobSkill 170 在旧端会 Flash。戴米安已投影成 100/101，不要改回 170，也不要占用 185/176。",
        }
    if skill_id in HARD_SKIN_IDS:
        return {
            "edit": False,
            "verdict": "skip",
            "reason": (
                "v83 的 142 是硬皮（HARD_SKIN），还有 hp 门槛。"
                "TMS 戴米安四个 skill 槽虽然也写 142，那是现代 FSM，不是这份表。"
                "不要改 142 来还原光球；A 应继续用投影 ID（100/101/123/128）。"
            ),
        }
    if skill_id not in index and skill_id not in MOB_SKILL_NAMES:
        return {
            "edit": False,
            "verdict": "forbidden",
            "reason": (
                f"类型 {skill_id} 不在旧端 MobSkill 表里。TMS _Canvas/{skill_id}.img "
                f"{'存在' if tms_canvas_file(skill_id).is_file() else '也没有'}，"
                "但不能整文件拷进 v83 MobSkill.img。应投影到已有 ID，战斗写 Java。"
            ),
        }
    if not has_level:
        return {
            "edit": True,
            "verdict": "need-level",
            "reason": (
                f"服务端 XML 没有 {skill_id}/level/{level}，怪物施放会拿不到 MobSkill。"
                "优先改 info/skill 去已有档；只有确认要全服新档时才增量插入这一级，禁止重写整份 MobSkill.img。"
            ),
        }
    if intercept or skill_id in JAVA_INTERCEPT_IDS:
        return {
            "edit": False,
            "verdict": "java-owns",
            "reason": (
                f"{skill_id} 的 applyEffect 已被 Boss 兼容类拦截。"
                "改 MobSkill.img 的 x/lt/interval 会作用到所有共用这一档的怪。"
                "戴米安光球/黑雾继续改 Java，不要改这份全局表。戴米安本体不要绑 176/185。"
            ),
        }
    if skill_id in DISEASE_IDS:
        return {
            "edit": False,
            "verdict": "shared-disease",
            "reason": (
                "这是全服疾病档。lt/rb/time 一改，所有用同一 ID+等级的怪都会变。"
                "戴米安 123/128 已在 Encounter 里用自己的抓取盒。单个 Boss 不要改 MobSkill。"
            ),
        }
    tms_note = ""
    if tms_skill_id is not None and tms_skill_id != skill_id:
        tms_note = f" TMS 槽位仍是 {tms_skill_id}，那是对照用，不要写回 A。"
    return {
        "edit": False,
        "verdict": "keep",
        "reason": (
            f"v83 已有 {skill_id}/level/{level}（{MOB_SKILL_NAMES.get(skill_id, skill_id)}）。"
            "只在要改『全服这一档』的冷却/持续时间/effect 贴图时才打开 MobSkill 编辑器。"
            + tms_note
        ),
    }


def mapping_card(
    skill_id: int | None,
    level: int | None,
    action: int | None,
    *,
    tms_skill_id: int | None = None,
    intercept: bool = False,
    mob_id: str = "",
) -> dict[str, Any]:
    index = server_index()
    record = index.get(skill_id) if skill_id is not None else None
    level_info = (record or {}).get("byLevel", {}).get(level or -1) if record else None
    files = [
        {
            "role": "怪物槽位",
            "path": f"Mob/{mob_id or '*'}.img → info/skill/*/skill={skill_id} level={level} action={action}",
        },
        {
            "role": "本体动作",
            "path": f"Mob/{mob_id or '*'}.img → skill{action}" if action else "无 action，不会播 skillN",
        },
        {
            "role": "旧端 MobSkill 表",
            "path": f"clien/Data/Skill/MobSkill.img → {skill_id}/level/{level}",
        },
        {
            "role": "服务端同一路径",
            "path": f"gms-server/wz/Skill.wz/MobSkill.img.xml → {skill_id}/level/{level}",
        },
    ]
    tms_id = tms_skill_id if tms_skill_id is not None else skill_id
    tms = tms_canvas_info(tms_id) if tms_id is not None else None
    if tms is not None:
        files.append({"role": "TMS 分文件像素库", "path": tms["path"]})
    return {
        "whatItDoes": WHAT_IT_DOES,
        "whenToEdit": WHEN_TO_EDIT,
        "whenNotToEdit": WHEN_NOT_TO_EDIT,
        "skillId": skill_id,
        "level": level,
        "action": action,
        "typeName": MOB_SKILL_NAMES.get(skill_id or -1, "未知/现代 ID" if skill_id else "未绑定"),
        "tmsSkillId": tms_skill_id,
        "serverHasSkill": skill_id in index if skill_id is not None else False,
        "serverLevels": (record or {}).get("levels") or [],
        "serverHasLevel": bool(level_info),
        "serverFields": (level_info or {}).get("fields") or {},
        "serverFolders": (level_info or {}).get("folders") or [],
        "tmsCanvas": tms,
        "files": files,
        "nodePath": f"{skill_id}/level/{level}" if skill_id is not None and level is not None else None,
        "advice": advice_for(skill_id, level, tms_skill_id=tms_skill_id, intercept=intercept),
        "clientImg": str(_CLIENT_IMG.relative_to(_ROOT)) if _CLIENT_IMG.is_file() else None,
    }


def from_slot(slot: dict[str, Any] | None, *, intercept_ids: set[int] | None = None, mob_id: str = "") -> dict[str, Any]:
    slot = slot or {}
    skill_id = _int(slot.get("skill"))
    level = _int(slot.get("level"))
    action = _int(slot.get("action"))
    tms_skill_id = _int(slot.get("tmsSkill"))
    intercept = bool(skill_id is not None and skill_id in (intercept_ids or JAVA_INTERCEPT_IDS))
    return mapping_card(
        skill_id, level, action,
        tms_skill_id=tms_skill_id, intercept=intercept, mob_id=mob_id,
    )


def from_path(path: str, slots: list[dict[str, Any]], mob_id: str = "") -> dict[str, Any] | None:
    parts = (path or "").split("/")
    action = None
    slot = None
    if parts and parts[0].startswith("skill") and parts[0][5:].isdigit():
        action = int(parts[0][5:])
        slot = next((item for item in slots if _int(item.get("action")) == action), None)
    elif len(parts) >= 3 and parts[0] == "info" and parts[1] == "skill" and parts[2].isdigit():
        index = int(parts[2])
        slot = next((item for item in slots if item.get("index") == index), None)
        action = _int((slot or {}).get("action"))
    if slot is None and action is None:
        return None
    return from_slot(slot, mob_id=mob_id)

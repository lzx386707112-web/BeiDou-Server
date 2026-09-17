#!/usr/bin/env python3
"""Old-client server-control skill help for the Map/Mob workbench.

Copying TMS ``skillN`` frames only restores the boss pose. Flying orbs, delayed
zones, and dummy-mob paths live in Java. This module classifies a selected node
and tells the user which proven template to start from.
"""

from __future__ import annotations

import re
from typing import Any

from . import mob_skill_resolve

VISUAL_MOB = "8880112"
JAVA_HOOK = "gms-server/src/main/java/org/gms/server/life/DamienBossCompat.java"

HOW_TO_START = [
    "先看节点类型：attackN 可能是近战、弹道、预警砸地，或 TMS onlyFsm 空姿势（复制成 stand UOL，不要留 1×1）。",
    "复制 info 时补 LifeFactory 必读字段（level/PADamage/PDDamage/MADamage/MDDamage），并把 TMS PDRate/MDRate>70 清成 0。戴米安技能表投影 100/101/123/128，禁止 170 Flash，也不占用 185/176。",
    "戴米安 skill2 从 0 播到 104：0–9 引用 skill1，10–30 新图，31–79 用 ../skill2/23–30 维持天上姿势，80–96 收招，97–104 回 stand。不要写成同目录 UOL 23，旧端会掉回 stand。",
    "对照 A 的 info/skill：skill=MobSkill 类型 ID，level=MobSkill.img/{id}/level/{n}，action=播 skill{action}。TMS 的 Skill/MobSkill/_Canvas/{id}.img 是该 ID 的分文件像素库，不是 v83 那份总表。",
    "不要为单个 Boss 改全局 MobSkill.img。光球/圈伤写 Java。只有全服共用档位（冷却、疾病时间、effect 贴图）缺失时才改 MobSkill。",
    "飞体不要塞进 skillN/ball。旧端弹道只认 attack*/info/ball 且 type=2；戴米安 skill2 刷 8880112（8880110 skill2/23–30 金火），禁止 8880102。",
    "戴米安只留投影 100/101/123/128 和 skill2 光球。不要恢复 handleMobSkill / onAttackHit / 刻印 / 飞剑 / MCV。",
    "伤害走客户端 TAKE_DAMAGE（金球 fixDamR=20）；不要给戴米安加 customBossDemian FIELD_EFFECT。",
    "改完用纯函数测条数/轨迹，再进图看本体动画、飞体、命中数字是否同帧。",
]

TEMPLATES = {
    "pose_only": {
        "id": "pose_only",
        "title": "仅本体动作",
        "summary": "客户端播 skillN/attackN 帧即可。服务端最多改冷却或百分比伤。",
        "start": "确认帧连续、UOL 目标在 A 里存在。Java 不必生成额外怪。",
    },
    "fsm_pose": {
        "id": "fsm_pose",
        "title": "TMS onlyFsm 空姿势",
        "summary": "现代端只靠 FSM 出招，身体常是 1×1 空帧。旧端会把该帧当姿势播，导致闪烁、反伤等特效掉到脚下。",
        "start": "复制时投影成 attack3 那种 ../stand/N UOL，不要留下 origin=(0,0) 的 1×1。命中仍看 info/hit。不要发明 ball。",
    },
    "ballistic": {
        "id": "ballistic",
        "title": "attack 弹道（type=2）",
        "summary": "info/ball + type=2 + bulletSpeed，命中走 TAKE_DAMAGE。一次攻击一条弹道。",
        "start": "对照 8641002。缺 type/bulletSpeed/hit.attach 时增量补字段，不要给近战发明 ball。",
    },
    "delayed_zone": {
        "id": "delayed_zone",
        "title": "预警后圈伤",
        "summary": "Mob areaWarning 只留画面；圈伤按客户端 attackAfter / TAKE_DAMAGE。不要 FIELD_EFFECT MCV。",
        "start": "MoveLifeHandler → onAttackStart(attackIndex) → showEffect；TimerManager.schedule(attackAfter) → applyZones。",
    },
    "spawn_visual": {
        "id": "spawn_visual",
        "title": "占位怪飞体（个数/轨迹）",
        "summary": "skillN 只播 Boss；N 个 8880112 金火按露希妲 setPosition+spawnMonster，弹道走 attack1/info/ball。",
        "start": (
            "1) 先复制 skill1，再复制 skill2。客户端从 skill2/0 连播到最后一帧。\n"
            "2) 0–9 必须是 ../skill1/N；31–79 必须是 ../skill2/23–30（旧端同目录 UOL 会闪回地面）。\n"
            "3) 射手必须是 8880112（8880110 skill2/23–30 金火），禁止 8880102。\n"
            "4) LifeFactory.getMonster(8880112)；setPosition(地板 perch)；spawnMonster；不要 resetMobPosition。"
        ),
    },
    "projected_mobskill": {
        "id": "projected_mobskill",
        "title": "投影 MobSkill",
        "summary": "info/skill 绑 100/101/123/128 等通用旧 ID，禁止 170 Flash，不要占用路西德 185、阿卡伊勒 176。",
        "start": "MoveLifeHandler 用 skill 动作下标 resolveCastSkill；handleMobSkill(skillId) 写规则。",
    },
    "info_copy": {
        "id": "info_copy",
        "title": "info 投影（可召唤）",
        "summary": "补齐 LifeFactory 无默认值字段，戴米安技能表改成 100/101/123/128。",
        "start": "先有 skill1–4（或当前 action 对应动作），再复制 info。缺 PDDamage 会 NPE。",
    },
}

_ATTACK = re.compile(r"^attack(\d+)(?:/.*)?$")
_SKILL = re.compile(r"^skill(\d+)(?:/.*)?$")

SKILL2_PLAYBACK = [
    "TMS 从 skill2/0 连播到 104，不是从 10 起。_Canvas 从 10 起号只因为前面没有独立像素。",
    "0–9：UOL ../skill1/0–9，同一套抬手。复制 skill2 之前必须先有 skill1。",
    "10–30：skill2 自己的大特效像素（原点跳到约 106,653）。",
    "31–71：循环天上姿势，旧端写成 ../skill2/23–30，不要 value=23。",
    "72–79：逻辑层 _outlink 到 23–30；旧端同样写成 ../skill2/N。",
    "80–96：收招新像素。97–104：UOL ../stand/0–7。",
]
SKILL4_PLAYBACK = [
    "TMS 从 skill4/0 连播；_Canvas 只有 2–41 的独立像素，0–1 不是缺资源。",
    "0–1：逻辑层 1×1 _outlink → skill3/0–1，复制成 UOL ../skill3/N。有 skill1 不够，要先有 skill3。",
    "2–41：skill4 自己的像素。",
    "42–43：_outlink → skill2/87–88，复制成 ../skill2/87 和 ../skill2/88。",
    "空 1×1 且没有 _outlink 的尾帧（如 44）不收录，不要用 stand 去填，也不要压成 0..n-1。",
]


INFO_COPY = [
    "LifeFactory 读 info 时 level/PADamage/PDDamage/MADamage/MDDamage 没有默认值，缺一项召唤就 NPE，客户端显示怪物不存在。",
    "TMS 戴米安常有 PDRate/MDRate 而没有 PDDamage/MDDamage。复制时自动补 0（或沿用 A 已有值），不要只拷 Rate。",
    "8880110 的 info/skill 投影 100/101/123/128（action 1–4）。不要占用 185/176。已有希纳斯表再复制 info 会整表替换。",
    "只写入当前 A 里已有动作的槽；skill3/4 还没拷时不会强行绑 action 3/4。先拷动作再拷 info。",
]


def action_frame_meaning(action: str, frame: str, *, value: str = "", outlink: str = "") -> str:
    """Explain one TMS action frame for the node-detail panel."""
    if not frame.isdigit():
        return ""
    index = int(frame)
    target = (value or "").replace("\\", "/").strip()
    link = (outlink or "").replace("\\", "/")
    if action == "skill2":
        if 0 <= index <= 9:
            return f"起手，复用 skill1/{index}（UOL ../skill1/{index}）。skill2 从 0 播，不是从 10 起。"
        if 10 <= index <= 22:
            return "skill2 独有特效帧。_Canvas 从这里才有独立像素。"
        if 23 <= index <= 30:
            return "循环姿势源帧。31–79 都回来播这 8 张。"
        if 31 <= index <= 71:
            loop = str(23 + ((index - 31) % 8))
            shown = target if target.startswith("../skill2/") else (
                f"../skill2/{target}" if target.isdigit() else f"../skill2/{loop}"
            )
            return f"循环站桩，UOL → {shown}（即 23–30）。不是缺帧，不要改成 stand，也不要写成同目录 23。"
        if 72 <= index <= 79:
            loop = str(23 + (index - 72))
            return f"再播一遍 23–30：逻辑层 _outlink 到 skill2/{loop}，复制成 ../skill2/{loop}。"
        if 80 <= index <= 96:
            return "收招像素，特效收回、身体回来。"
        if 97 <= index <= 104:
            return f"回站立，UOL ../stand/{index - 97}。"
        if target.startswith("../skill1/"):
            return f"起手引用 {target}"
        if target.startswith("../stand/"):
            return f"收招引用 {target}"
        if target.isdigit():
            return f"循环引用本动作第 {target} 帧"
        if "/skill2/" in link:
            return f"与 {link.rsplit('/', 1)[-1]} 同像素（_outlink）"
    if action == "skill4":
        if index <= 1:
            return f"起手复用 skill3/{index}。TMS 是 1×1 _outlink，复制成 ../skill3/{index}，不是 skill1。"
        if 2 <= index <= 41:
            return "skill4 独有像素。_Canvas 从 2 起才有独立画布。"
        if index in {42, 43}:
            target_frame = 87 if index == 42 else 88
            return f"收招复用 skill2/{target_frame}（_outlink），复制成 ../skill2/{target_frame}。"
        if index == 44:
            return "空 1×1 且无 _outlink，旧端不收录。"
        if target.startswith("../skill3/"):
            return f"起手引用 {target}"
        if target.startswith("../skill2/"):
            return f"收招引用 {target}"
    if action == "skill1":
        if index <= 4:
            return "skill1 可见抬手。skill2/0–4 会 UOL 到这里。"
        if 5 <= index <= 9:
            return "skill1 隐藏帧（hide=1）。skill2/5–9 仍引用它们。"
        if index == 10:
            return "skill1 结尾空帧；skill2 不引用这一帧。"
    if action == "attack3" and target.startswith("../stand/"):
        return f"真实 UOL {target}，身体复用站立。"
    if target.startswith("../stand/"):
        return f"复用站立 {target}"
    if target.startswith("../skill"):
        return f"复用 {target}。复制前目标动作必须已在 A 中。"
    if target.isdigit():
        return f"循环播放本动作第 {target} 帧"
    return ""


def skill_slots_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slots: dict[int, dict[str, Any]] = {}
    for row in rows:
        parts = str(row.get("path") or "").split("/")
        if len(parts) != 4 or parts[0] != "info" or parts[1] != "skill":
            continue
        try:
            index = int(parts[2])
        except ValueError:
            continue
        slot = slots.setdefault(index, {"index": index})
        left = row.get("left") or {}
        right = row.get("right") or {}
        field = parts[3]
        if left.get("value") is not None:
            slot[field] = left.get("value")
        elif field not in slot:
            slot[field] = right.get("value")
        if field == "skill" and right.get("value") is not None:
            slot["tmsSkill"] = right.get("value")
    return [slots[index] for index in sorted(slots)]


def classify(path: str, rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = rows or []
    root = path.split("/", 1)[0] if path else ""
    slots = skill_slots_from_rows(rows)
    attack = _ATTACK.match(path or "")
    skill = _SKILL.match(path or "")

    has_ball = any(
        str(row.get("path") or "").startswith(f"{root}/info/ball") for row in rows
    ) if root.startswith("attack") else False
    has_warning = any(
        str(row.get("path") or "").startswith(f"{root}/info/areaWarning") for row in rows
    ) if root.startswith("attack") else False
    type_value = None
    attack_after = None
    only_fsm = False
    for row in rows:
        if row.get("path") == f"{root}/info/type":
            type_value = (row.get("left") or row.get("right") or {}).get("value")
        if row.get("path") == f"{root}/info/attackAfter":
            attack_after = (row.get("left") or row.get("right") or {}).get("value")
        if row.get("path") == f"{root}/info/onlyFsm":
            only_fsm = str((row.get("left") or row.get("right") or {}).get("value")) in {"1", "1.0", "true"}

    if attack:
        index = int(attack.group(1)) - 1
        if has_ball or str(type_value) == "2":
            template = TEMPLATES["ballistic"]
            playback = "旧端播 ball 弹道；Boss 若无 attack 帧则可能只有刀光没有挥砍姿势。"
            java_hint = f"TakeDamageHandler → onAttackHit(mob, {index})；fixedDamagePercent 用这个下标。"
        elif has_warning:
            template = TEMPLATES["delayed_zone"]
            playback = f"旧端播 areaWarning/hit；圈伤对齐 attackAfter={attack_after}。不要 damien-ground.mcv。"
            java_hint = f"MoveLifeHandler → onAttackStart(mob, {index})；圈伤 delay=XML attackAfter。"
        elif only_fsm:
            template = TEMPLATES["fsm_pose"]
            playback = "旧端不认 onlyFsm，会播身体帧。复制后应为 stand UOL，特效挂 stand 原点。"
            java_hint = f"TakeDamageHandler → onAttackHit(mob, {index})；不要给该招发明 ball。"
        else:
            template = TEMPLATES["pose_only"]
            playback = "旧端播 attack 动作；命中走 TAKE_DAMAGE。"
            java_hint = f"TakeDamageHandler → onAttackHit(mob, {index})；fixedDamagePercent 用这个下标。"
        return {
            "kind": "attack",
            "action": f"attack{index + 1}",
            "attackIndex": index,
            "template": template,
            "playback": playback,
            "javaHint": java_hint,
            "slots": slots,
        }

    if skill:
        action = int(skill.group(1))
        bound = next((slot for slot in slots if int(slot.get("action") or 0) == action), None)
        template = TEMPLATES["spawn_visual"] if action == 2 else TEMPLATES["projected_mobskill"]
        if action != 2 and not bound:
            template = TEMPLATES["pose_only"]
        playback = "旧端只播 skill 文件夹里的 Canvas/UOL，不会读取光球个数或轨迹。"
        timeline: list[str] = []
        if action == 2:
            playback = " ".join(SKILL2_PLAYBACK)
            timeline = SKILL2_PLAYBACK
        elif action == 4:
            playback = " ".join(SKILL4_PLAYBACK)
            timeline = SKILL4_PLAYBACK
        skill_id = bound.get("skill") if bound else None
        return {
            "kind": "skill",
            "action": f"skill{action}",
            "attackIndex": None,
            "template": template,
            "playback": playback,
            "javaHint": (
                f"info/skill 投影 ID={skill_id}，handleMobSkill({skill_id})。"
                if skill_id else
                "info/skill 未找到对应 action；先核对技能槽再写 Java。"
            ),
            "slots": slots,
            "projectedSkill": skill_id,
            "timeline": timeline,
        }

    if path.startswith("info/skill"):
        return {
            "kind": "skill-slot",
            "action": path,
            "template": TEMPLATES["projected_mobskill"],
            "playback": "技能槽决定客户端播 skillN 以及服务端 apply 哪个 MobSkill。",
            "javaHint": "LifeFactory 按 0..n 顺序写入 LinkedHashSet；resolveCastSkill 依赖这个顺序。",
            "slots": slots,
        }

    if path == "info" or path.startswith("info/"):
        return {
            "kind": "info",
            "action": path,
            "template": TEMPLATES["info_copy"],
            "playback": " ".join(INFO_COPY),
            "javaHint": "SpawnCommand / LifeFactory.getMonsterStats 读这些字段；NPE 时客户端显示怪物不存在。",
            "slots": slots,
            "timeline": INFO_COPY,
        }

    return {
        "kind": "other",
        "action": path,
        "template": TEMPLATES["pose_only"],
        "playback": "该节点通常不是服务端飞体入口。",
        "javaHint": "若需要个数/轨迹，从最近的 skillN 或 attackN 往上看。",
        "slots": slots,
    }


def related_resources(path: str, mob_id: str) -> list[dict[str, str]]:
    items = [
        {"kind": "java", "name": "DamienBossCompat", "path": JAVA_HOOK},
        {"kind": "mob", "name": VISUAL_MOB, "path": f"clien/Data/Mob/{VISUAL_MOB}.img"},
    ]
    if "/info/ball" in f"/{path}/" or (path or "").endswith("/info/ball"):
        items.append({
            "kind": "ball",
            "name": "attack2/info/ball",
            "path": f"clien/Data/Mob/{mob_id or '8880110'}.img",
        })
    return items


def help_for(path: str, rows: list[dict[str, Any]] | None = None, mob_id: str = "") -> dict[str, Any]:
    classified = classify(path, rows)
    template = classified["template"]
    return {
        "path": path,
        "mobId": mob_id,
        "howToStart": HOW_TO_START,
        "kind": classified.get("kind"),
        "action": classified.get("action"),
        "attackIndex": classified.get("attackIndex"),
        "playback": classified.get("playback"),
        "timeline": classified.get("timeline") or [],
        "javaHint": classified.get("javaHint"),
        "projectedSkill": classified.get("projectedSkill"),
        "slots": classified.get("slots") or [],
        "template": template,
        "templates": list(TEMPLATES.values()),
        "related": related_resources(path, mob_id),
        "mobSkill": mob_skill_resolve.from_path(path, classified.get("slots") or [], mob_id),
        "mobSkillGuide": {
            "whatItDoes": mob_skill_resolve.WHAT_IT_DOES,
            "whenToEdit": mob_skill_resolve.WHEN_TO_EDIT,
            "whenNotToEdit": mob_skill_resolve.WHEN_NOT_TO_EDIT,
        },
    }


def should_attach(path: str) -> bool:
    if str(path).startswith("info/skill"):
        return str(path).count("/") <= 3
    parts = str(path).split("/")
    if not parts or not re.match(r"^(attack|skill)\d+$", parts[0]):
        return False
    if len(parts) == 1:
        return True
    if parts[1:] == ["info"]:
        return True
    return parts[1:] == ["info", "ball"]


def attach(rows: list[dict[str, Any]], mob_id: str) -> None:
    for row in rows:
        path = str(row.get("path") or "")
        if should_attach(path):
            row["serverControl"] = help_for(path, rows, mob_id)

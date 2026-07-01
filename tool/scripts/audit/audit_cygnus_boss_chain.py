#!/usr/bin/env python3
"""Audit Cygnus boss-chain mob skill references against the current client."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import WzImage, WzKey  # noqa: E402


KEY = WzKey.for_region("GMS")
CLIENT = ROOT / "clien/Data"
MOB_IDS = [str(mid) for mid in range(8850000, 8850014)] + [
    str(mid) for mid in range(8610010, 8610016)
]


def load_img(path: Path) -> WzImage:
    img = WzImage.from_bytes(path.read_bytes(), key=KEY, name=path.name)
    img.parse()
    return img


def child(node, name: str):
    return node.child(name) if node is not None and hasattr(node, "child") else None


def value(node, default=None):
    return getattr(node, "value", default) if node is not None else default


def as_int(raw) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def main() -> int:
    mob_skill = load_img(CLIENT / "Skill/MobSkill.img")
    max_levels: dict[int, int] = {}
    for skill_node in mob_skill.root.children():
        sid = as_int(skill_node.name)
        if sid is None or not hasattr(skill_node, "children"):
            continue
        level_root = child(skill_node, "level")
        if level_root is None:
            continue
        levels = [as_int(c.name) for c in level_root.children()]
        levels = [lv for lv in levels if lv is not None]
        if levels:
            max_levels[sid] = max(levels)

    problems: list[str] = []
    print("MobSkill supported max levels:")
    for sid in sorted(max_levels):
        print(f"  {sid}: {max_levels[sid]}")

    for mid in MOB_IDS:
        img = load_img(CLIENT / f"Mob/{mid}.img")

        skills = child(child(img.root, "info"), "skill")
        if skills is not None:
            for entry in skills.children():
                sid = as_int(value(child(entry, "skill")))
                level = as_int(value(child(entry, "level")))
                if sid is None or level is None:
                    continue
                max_level = max_levels.get(sid)
                if max_level is None:
                    problems.append(f"{mid} info/skill/{entry.name}: missing MobSkill {sid}/{level}")
                elif level > max_level:
                    problems.append(
                        f"{mid} info/skill/{entry.name}: level {sid}/{level} > client max {max_level}"
                    )

        for attack in img.root.children():
            if not attack.name.startswith("attack"):
                continue
            info = child(attack, "info")
            disease = as_int(value(child(info, "disease")))
            level = as_int(value(child(info, "level")))
            if disease is None or level is None:
                continue
            max_level = max_levels.get(disease)
            if max_level is None:
                problems.append(f"{mid} {attack.name}/info: missing disease {disease}/{level}")
            elif level > max_level:
                problems.append(
                    f"{mid} {attack.name}/info: disease {disease}/{level} > client max {max_level}"
                )

    if problems:
        print("\nProblems:")
        for item in problems:
            print(f"  - {item}")
        return 1

    print("\nProblems: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

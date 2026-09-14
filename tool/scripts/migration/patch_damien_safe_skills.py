#!/usr/bin/env python3
"""Keep Damien scene/ground skills off huge TMS action frames that crash the old client."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
from migrate_twilight_perion_monster_park import load_checked  # noqa: E402
from wzpy import WzImage  # noqa: E402


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def set_int_img(path: Path, record_path: tuple[str, ...], value: int) -> None:
    original = path.read_bytes()
    image = load_checked(path, arc.GMS_KEY)
    node = image.root.get("/".join(record_path))
    if node is None:
        raise RuntimeError(f"{path.name} missing {'/'.join(record_path)}")
    if int(node.value) == value:
        return
    patched = arc.mutate_img(original, "edit", record_path, values={"value": value}, region="GMS").data
    arc.verify_raw_record_scope(original, patched, {record_path}, allow_additions=False)
    checked = WzImage.from_bytes(patched, key=arc.GMS_KEY, name=path.name)
    checked.parse()
    if checked.truncated or checked.parse_warnings:
        raise RuntimeError(f"{path.name} parse failed after {record_path}")
    arc.atomic_write_bytes(path, patched)


def xml_imgdir_span(text: str, name: str, start_at: int = 0) -> tuple[int, int]:
    token = f'<imgdir name="{name}">'
    start = text.find(token, start_at)
    if start < 0:
        raise RuntimeError(f"XML imgdir {name} not found")
    depth = 0
    idx = start
    while True:
        next_open = text.find("<imgdir", idx)
        next_close = text.find("</imgdir>", idx)
        if next_close < 0:
            raise RuntimeError(f"XML imgdir {name} end not found")
        if 0 <= next_open < next_close:
            depth += 1
            idx = next_open + 7
        else:
            depth -= 1
            if depth == 0:
                return start, next_close + len("</imgdir>")
            idx = next_close + 9


def set_xml_only_fsm(mob_id: int, attack: str, value: int) -> None:
    xml = demian.server_mob_path("wz", mob_id)
    text = xml.read_text(encoding="utf-8")
    start, end = xml_imgdir_span(text, attack)
    chunk = text[start:end]
    old = 'name="onlyFsm" value="0"' if value == 1 else 'name="onlyFsm" value="1"'
    new = f'name="onlyFsm" value="{value}"'
    if old not in chunk:
        if new in chunk:
            return
        raise RuntimeError(f"{mob_id} XML {attack} onlyFsm not found")
    arc.atomic_write_text(xml, text[:start] + chunk.replace(old, new, 1) + text[end:])


def set_xml_skill_action(mob_id: int, skill_id: int, action: int) -> None:
    xml = demian.server_mob_path("wz", mob_id)
    text = xml.read_text(encoding="utf-8")
    marker = f'<int name="skill" value="{skill_id}"/>'
    skill_at = text.find(marker)
    if skill_at < 0:
        raise RuntimeError(f"{mob_id} XML missing skill {skill_id}")
    action_at = text.find('<int name="action" value="', skill_at)
    action_end = text.find("/>", action_at)
    current = text[action_at:action_end]
    wanted = f'<int name="action" value="{action}"'
    if current == wanted:
        return
    arc.atomic_write_text(xml, text[:action_at] + wanted + text[action_end:])


def skill_index(image, skill_id: int) -> str:
    skill = image.root.get("info/skill")
    for child in skill.children():
        if int(arc.child_value(child, "skill") or 0) == skill_id:
            return child.name
    raise RuntimeError(f"missing skill {skill_id}")


def patch_mob(mob_id: int, attack: str, scene_action: int) -> None:
    client = demian.client_mob_path(mob_id)
    image = load_checked(client, arc.GMS_KEY)
    set_int_img(client, (attack, "info", "onlyFsm"), 1)
    index = skill_index(image, 176)
    set_int_img(client, ("info", "skill", index, "action"), scene_action)
    set_xml_only_fsm(mob_id, attack, 1)
    set_xml_skill_action(mob_id, 176, scene_action)


def main() -> int:
    targets = (
        demian.client_mob_path(8880110),
        demian.client_mob_path(8880111),
        demian.server_mob_path("wz", 8880110),
        demian.server_mob_path("wz", 8880111),
    )
    patch_mob(8880110, "attack2", 1)
    patch_mob(8880111, "attack3", 1)
    first = {str(path): sha256_file(path) for path in targets}
    patch_mob(8880110, "attack2", 1)
    patch_mob(8880111, "attack3", 1)
    second = {str(path): sha256_file(path) for path in targets}
    if first != second:
        raise RuntimeError(f"safe-skill patcher is not idempotent: {first} vs {second}")
    print("damien safe-skill patch ok")
    for path, digest in first.items():
        print(f"{Path(path).relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

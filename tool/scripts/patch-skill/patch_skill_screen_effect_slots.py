#!/usr/bin/env python3
"""Mirror skill screen nodes into old-client effect slots.

BeiDou.exe's old skill visual loader does not have native `screen` slots.
The companion EXE hook plays high effect indices 90..93 after the regular
skill effect, so this script mirrors common screen node names into those
indices:

    screen  -> effect/90
    screen0 -> effect/91
    screen1 -> effect/92
    screen2 -> effect/93

Pass one or more skill ids to patch. Use --all only when intentionally
scanning every client Skill/*.img and server Skill.wz/*.img.xml.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
sys.path.insert(0, str(WZPY))
sys.path.insert(0, str(PATCH_SKILL))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzSubProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402

from patch_1121001_sword_illusion import (  # noqa: E402
    clone_property,
    find_canvas_element_end,
    find_imgdir_block,
    replace_child,
    replace_or_append_child_xml,
)
from patch_1121012_test_skill import atomic_write_bytes, atomic_write_text, backup  # noqa: E402


CLIENT_SKILL_DIR = ROOT / "clien" / "Data" / "Skill"
SERVER_SKILL_DIR = ROOT / "gms-server" / "wz" / "Skill.wz"
TARGET_KEY = WzKey.for_region("GMS")

SCREEN_EFFECT_SLOTS = (
    ("screen", "90"),
    ("screen0", "91"),
    ("screen1", "92"),
    ("screen2", "93"),
)


def wanted_job_files(skill_ids: set[str]) -> set[str] | None:
    if not skill_ids:
        return None
    return {skill_id[:3] for skill_id in skill_ids}


def iter_client_skill_files(skill_ids: set[str]) -> list[Path]:
    jobs = wanted_job_files(skill_ids)
    files = sorted(CLIENT_SKILL_DIR.glob("*.img"))
    if jobs is None:
        return files
    return [path for path in files if path.stem in jobs]


def iter_server_skill_files(skill_ids: set[str]) -> list[Path]:
    jobs = wanted_job_files(skill_ids)
    files = sorted(SERVER_SKILL_DIR.glob("*.img.xml"))
    if jobs is None:
        return files
    return [path for path in files if path.name.removesuffix(".img.xml") in jobs]


def ensure_effect_node(skill: WzSubProperty) -> WzSubProperty:
    effect = skill.child("effect")
    if not isinstance(effect, WzSubProperty):
        effect = WzSubProperty("effect", skill)
        replace_child(skill, effect)
    return effect


def property_signature(prop):
    if prop is None:
        return None
    if isinstance(prop, WzCanvasProperty):
        return (
            type(prop).__name__,
            prop.name,
            prop.width,
            prop.height,
            tuple(property_signature(child) for child in prop.children()),
        )
    if isinstance(prop, WzSubProperty):
        return (
            type(prop).__name__,
            prop.name,
            tuple(property_signature(child) for child in prop.children()),
        )
    return (
        type(prop).__name__,
        prop.name,
        getattr(prop, "value", None),
        getattr(prop, "x", None),
        getattr(prop, "y", None),
    )


def patch_client_skill_file(path: Path, skill_ids: set[str], dry_run: bool) -> int:
    image = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    root = image.parse()
    skill_root = root.get("skill")
    if not isinstance(skill_root, WzSubProperty):
        return 0

    changed = 0
    mirrored: list[str] = []
    for skill in list(skill_root.children()):
        if not isinstance(skill, WzSubProperty):
            continue
        if skill_ids and skill.name not in skill_ids:
            continue
        effect = ensure_effect_node(skill)
        for source_name, target_index in SCREEN_EFFECT_SLOTS:
            source = skill.child(source_name)
            if source is None:
                continue
            clone = clone_property(source, target_index, effect)
            existing = effect.child(target_index)
            if property_signature(existing) == property_signature(clone):
                continue
            if existing is not None:
                raise RuntimeError(
                    f"{path} skill/{skill.name}/effect/{target_index} already exists; "
                    "choose a different compatibility slot before mirroring screen nodes"
                )
            replace_child(effect, clone)
            changed += 1
            mirrored.append(f"{skill.name}/{source_name}->effect/{target_index}")

    if changed == 0:
        return 0
    if dry_run:
        print(f"[dry-run] would mirror client screen slots in {path}: {', '.join(mirrored)}")
        return changed
    backup(path, ".bak-skill-screen-effect-slots", dry_run=False)
    atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    print(f"mirrored client screen slots in {path}: {', '.join(mirrored)}")
    return changed


def find_named_xml_block(block: str, child_name: str) -> tuple[int, int] | None:
    imgdir_token = f'<imgdir name="{child_name}"'
    imgdir_start = block.find(imgdir_token)
    if imgdir_start >= 0:
        return find_imgdir_block(block, child_name)

    canvas_token = f'<canvas name="{child_name}"'
    canvas_start = block.find(canvas_token)
    if canvas_start >= 0:
        return canvas_start, find_canvas_element_end(block, canvas_start)
    return None


def clone_named_xml_block(block: str, child_name: str, target_name: str) -> str | None:
    span = find_named_xml_block(block, child_name)
    if span is None:
        return None
    child_xml = block[span[0] : span[1]]
    return re.sub(
        rf'(<(?:imgdir|canvas) name=)"{re.escape(child_name)}"',
        rf'\1"{target_name}"',
        child_xml,
        count=1,
    )


def equivalent_xml(a: str, b: str) -> bool:
    return re.sub(r"\s+", "", a) == re.sub(r"\s+", "", b)


def ensure_effect_xml_block(skill_block: str) -> tuple[str, str]:
    try:
        effect_start, effect_end = find_imgdir_block(skill_block, "effect")
        return skill_block, skill_block[effect_start:effect_end]
    except RuntimeError:
        effect_block = '<imgdir name="effect"></imgdir>'
        insert_at = skill_block.rfind("</imgdir>")
        if insert_at < 0:
            raise RuntimeError("missing skill closing imgdir")
        return skill_block[:insert_at] + effect_block + skill_block[insert_at:], effect_block


def patch_server_skill_file(path: Path, skill_ids: set[str], dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")
    changed = 0
    mirrored: list[str] = []

    candidate_ids = sorted(skill_ids) if skill_ids else sorted(set(re.findall(r'<imgdir name="(\d{7,8})"', text)))
    for skill_id in candidate_ids:
        if skill_ids and skill_id not in skill_ids:
            continue
        try:
            skill_start, skill_end = find_imgdir_block(text, skill_id)
        except RuntimeError:
            continue
        skill_block = text[skill_start:skill_end]
        new_skill_block, effect_block = ensure_effect_xml_block(skill_block)
        skill_changed = 0
        for source_name, target_index in SCREEN_EFFECT_SLOTS:
            clone = clone_named_xml_block(new_skill_block, source_name, target_index)
            if clone is None:
                continue
            target_span = find_named_xml_block(effect_block, target_index)
            if target_span is not None and equivalent_xml(effect_block[target_span[0] : target_span[1]], clone):
                continue
            if target_span is not None:
                raise RuntimeError(
                    f"{path} skill/{skill_id}/effect/{target_index} already exists; "
                    "choose a different compatibility slot before mirroring screen nodes"
                )
            effect_block = replace_or_append_child_xml(effect_block, target_index, clone)
            changed += 1
            skill_changed += 1
            mirrored.append(f"{skill_id}/{source_name}->effect/{target_index}")
        if skill_changed:
            new_skill_block = replace_or_append_child_xml(new_skill_block, "effect", effect_block)
            text = text[:skill_start] + new_skill_block + text[skill_end:]

    if changed == 0:
        return 0
    if dry_run:
        print(f"[dry-run] would mirror server screen slots in {path}: {', '.join(mirrored)}")
        return changed
    backup(path, ".bak-skill-screen-effect-slots", dry_run=False)
    atomic_write_text(path, text)
    print(f"mirrored server screen slots in {path}: {', '.join(mirrored)}")
    return changed


def normalize_skill_ids(values: list[str]) -> set[str]:
    out: set[str] = set()
    for value in values:
        for part in re.split(r"[,\s]+", value):
            if part:
                out.add(part)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_ids", nargs="*", help="optional skill ids to patch, e.g. 1121001 1121012")
    parser.add_argument("--all", action="store_true", help="scan every skill file instead of requiring skill ids")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--client-only", action="store_true")
    parser.add_argument("--server-only", action="store_true")
    args = parser.parse_args()

    if args.client_only and args.server_only:
        raise SystemExit("--client-only and --server-only cannot be used together")

    skill_ids = normalize_skill_ids(args.skill_ids)
    if not skill_ids and not args.all:
        print("no skill ids supplied; pass explicit ids or --all to mirror screen nodes")
        return 0
    total = 0
    if not args.server_only:
        for path in iter_client_skill_files(skill_ids):
            total += patch_client_skill_file(path, skill_ids, args.dry_run)
    if not args.client_only:
        for path in iter_server_skill_files(skill_ids):
            total += patch_server_skill_file(path, skill_ids, args.dry_run)

    if total == 0:
        scope = ", ".join(sorted(skill_ids)) if skill_ids else "all skills"
        print(f"no skill screen nodes to mirror for {scope}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Remove superseded Dawn Warrior Canvas/test resources after MCV export."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WZPY = ROOT / "tool" / "wz-python"
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
sys.path.insert(0, str(WZPY))
sys.path.insert(0, str(PATCH_SKILL))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzSubProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402

from patch_1121001_sword_illusion import find_imgdir_block  # noqa: E402


CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "1112.img"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
CLIENT_MAP_EFFECT = ROOT / "clien" / "Data" / "Map" / "Effect.img"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "1112.img.xml"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"
TEST_SKILL_ID = "11121013"
VIDEO_EFFECT_NODES = (
    "galaxyStarBurst",
    "galaxyStarBurstBackground",
    "fullEclipseMale",
    "fullEclipseFemale",
    "soulEclipse",
    "soulEclipseStreamTest",
    "soulEclipseStreamBackground",
)
VIDEO_FIELD_MARKERS = (
    "galaxyStarBurstVideoLayer",
    "eclipseForceVideoLayer",
    "soulEclipseVideoLayer",
)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
    ) as output:
        output.write(data)
        temporary = Path(output.name)
    temporary.replace(path)


def atomic_write_text(path: Path, data: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
    ) as output:
        output.write(data)
        temporary = Path(output.name)
    temporary.replace(path)


def patch_client_image(path: Path, remover, dry_run: bool) -> None:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    remover(root)
    if not dry_run:
        atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))


def remove_test_skill(root: WzSubProperty) -> None:
    skill_root = root.get("skill")
    if isinstance(skill_root, WzSubProperty):
        skill_root._children.pop(TEST_SKILL_ID, None)
    root._children.pop(TEST_SKILL_ID, None)


def remove_video_effects(root: WzSubProperty) -> None:
    parent = root.get("customSkill/dawnWarrior")
    if not isinstance(parent, WzSubProperty):
        raise RuntimeError("missing customSkill/dawnWarrior in Effect.img")
    for name in VIDEO_EFFECT_NODES:
        parent._children.pop(name, None)


def remove_xml_node(text: str, node_name: str) -> str:
    try:
        start, end = find_imgdir_block(text, node_name)
    except RuntimeError:
        return text
    line_start = text.rfind("\n", 0, start) + 1
    if not text[line_start:start].strip():
        start = line_start
    if end < len(text) and text[end] == "\n":
        end += 1
    return text[:start] + text[end:]


def patch_server_xml(path: Path, dry_run: bool) -> None:
    updated = remove_xml_node(path.read_text(encoding="utf-8"), TEST_SKILL_ID)
    if not dry_run:
        atomic_write_text(path, updated)


def validate() -> None:
    skill = WzImage.from_bytes(
        CLIENT_SKILL.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_SKILL.name
    ).parse()
    strings = WzImage.from_bytes(
        CLIENT_STRING.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_STRING.name
    ).parse()
    effects = WzImage.from_bytes(
        CLIENT_MAP_EFFECT.read_bytes(), key=WzKey.for_region("GMS"), name=CLIENT_MAP_EFFECT.name
    ).parse()
    if skill.get(f"skill/{TEST_SKILL_ID}") is not None or strings.get(TEST_SKILL_ID) is not None:
        raise RuntimeError("test skill still exists in client data")
    for name in VIDEO_EFFECT_NODES:
        if effects.get(f"customSkill/dawnWarrior/{name}") is not None:
            raise RuntimeError(f"superseded Canvas effect still exists: {name}")
    for name in VIDEO_FIELD_MARKERS:
        marker = effects.get(f"customSkill/dawnWarrior/{name}/0")
        if not isinstance(marker, WzCanvasProperty) or (
            int(marker.width), int(marker.height)
        ) != (7, 5):
            raise RuntimeError(f"missing video field-layer marker: {name}")
    for path in (SERVER_SKILL, SERVER_STRING):
        try:
            find_imgdir_block(path.read_text(encoding="utf-8"), TEST_SKILL_ID)
        except RuntimeError:
            continue
        raise RuntimeError(f"test skill still exists in {path}")
    print("validated formal video skills: test skill and superseded Canvas effects removed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        validate()
        return 0
    patch_client_image(CLIENT_SKILL, remove_test_skill, args.dry_run)
    patch_client_image(CLIENT_STRING, remove_test_skill, args.dry_run)
    patch_client_image(CLIENT_MAP_EFFECT, remove_video_effects, args.dry_run)
    patch_server_xml(SERVER_SKILL, args.dry_run)
    patch_server_xml(SERVER_STRING, args.dry_run)
    if args.dry_run:
        print("dry-run: would remove test skill and superseded Canvas field effects")
    else:
        validate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Move the 2311006 Summon Dragon sprite 20 pixels away from the caster."""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzVectorProperty  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


SKILL_ID = "2311006"
X_OFFSET = 20
CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill" / "231.img"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz" / "231.img.xml"

FRAME_ORIGINS = {
    "summoned": [(42, 134), (42, 134), (42, 134), (42, 134), (42, 135)],
    "fly": [(42, 134), (42, 134), (42, 134), (42, 134), (42, 135)],
    "stand": [(43, 139), (43, 141), (43, 142), (43, 139), (43, 139)],
    "attack1": [
        (63, 144),
        (60, 143),
        (56, 150),
        (113, 141),
        (107, 141),
        (91, 138),
        (92, 143),
        (92, 143),
    ],
    "die": [(63, 164), (54, 163), (49, 167), (47, 152), (37, 154), (37, 156)],
}


def atomic_write_bytes(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def atomic_write_text(path: Path, data: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def find_imgdir_block(text: str, node_name: str) -> tuple[int, int]:
    token = f'<imgdir name="{node_name}">'
    start = text.find(token)
    if start < 0:
        raise RuntimeError(f"missing XML imgdir {node_name}")
    depth = 0
    for match in re.finditer(r"</?imgdir\b[^>]*>", text[start:]):
        tag = match.group(0)
        if tag.startswith("</"):
            depth -= 1
            if depth == 0:
                return start, start + match.end()
        elif not tag.endswith("/>"):
            depth += 1
    raise RuntimeError(f"unterminated XML imgdir {node_name}")


def desired_origin(origin: tuple[int, int]) -> tuple[int, int]:
    return origin[0] + X_OFFSET, origin[1]


def patch_client(path: Path, *, dry_run: bool, verify: bool) -> bool:
    image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    summon = root.get(f"skill/{SKILL_ID}/summon")
    if summon is None:
        raise RuntimeError(f"missing client skill/{SKILL_ID}/summon")

    changed = False
    for group_name, expected_origins in FRAME_ORIGINS.items():
        group = summon.get(group_name)
        if group is None:
            raise RuntimeError(f"missing client summon group {group_name}")
        frames = [child for child in group.children() if isinstance(child, WzCanvasProperty)]
        if [frame.name for frame in frames] != [str(index) for index in range(len(expected_origins))]:
            raise RuntimeError(f"unexpected client frames in summon/{group_name}")
        for frame, original in zip(frames, expected_origins):
            origin = frame.get("origin")
            target = desired_origin(original)
            if not isinstance(origin, WzVectorProperty):
                raise RuntimeError(f"missing client origin in summon/{group_name}/{frame.name}")
            current = (int(origin.x), int(origin.y))
            if current not in (original, target):
                raise RuntimeError(
                    f"unexpected client origin in summon/{group_name}/{frame.name}: {current}"
                )
            if verify and current != target:
                raise RuntimeError(
                    f"unpatched client origin in summon/{group_name}/{frame.name}: {current}"
                )
            if not verify and current != target:
                frame._children["origin"] = WzVectorProperty("origin", target[0], target[1], frame)
                changed = True

    if changed and not dry_run:
        atomic_write_bytes(path, encode_image_body(image, image.wz_file.reader))
    return changed


def patch_group_xml(
    group: str,
    group_name: str,
    expected_origins: list[tuple[int, int]],
    *,
    verify: bool,
) -> tuple[str, bool]:
    search_from = 0
    if group_name == "attack1":
        _, info_end = find_imgdir_block(group, "info")
        search_from = info_end

    changed = False
    cursor = search_from
    for frame_name, original in enumerate(expected_origins):
        token = f'<canvas name="{frame_name}" '
        frame_start = group.find(token, cursor)
        if frame_start < 0:
            raise RuntimeError(f"missing XML frame summon/{group_name}/{frame_name}")
        frame_end = group.find("</canvas>", frame_start)
        if frame_end < 0:
            raise RuntimeError(f"unterminated XML frame summon/{group_name}/{frame_name}")
        frame_end += len("</canvas>")
        frame = group[frame_start:frame_end]
        match = re.search(r'<vector name="origin" x="(-?\d+)" y="(-?\d+)"/>', frame)
        if match is None:
            raise RuntimeError(f"missing XML origin in summon/{group_name}/{frame_name}")

        current = int(match.group(1)), int(match.group(2))
        target = desired_origin(original)
        if current not in (original, target):
            raise RuntimeError(f"unexpected XML origin in summon/{group_name}/{frame_name}: {current}")
        if verify and current != target:
            raise RuntimeError(f"unpatched XML origin in summon/{group_name}/{frame_name}: {current}")
        if not verify and current != target:
            replacement = f'<vector name="origin" x="{target[0]}" y="{target[1]}"/>'
            group = group[:frame_start] + frame.replace(match.group(0), replacement, 1) + group[frame_end:]
            frame_end += len(replacement) - len(match.group(0))
            changed = True
        cursor = frame_end
    return group, changed


def patch_server(path: Path, *, dry_run: bool, verify: bool) -> bool:
    text = path.read_text(encoding="utf-8")
    skill_start, skill_end = find_imgdir_block(text, SKILL_ID)
    skill = text[skill_start:skill_end]
    summon_start, summon_end = find_imgdir_block(skill, "summon")
    summon = skill[summon_start:summon_end]

    changed = False
    for group_name, expected_origins in FRAME_ORIGINS.items():
        group_start, group_end = find_imgdir_block(summon, group_name)
        group, group_changed = patch_group_xml(
            summon[group_start:group_end], group_name, expected_origins, verify=verify
        )
        summon = summon[:group_start] + group + summon[group_end:]
        changed = changed or group_changed

    if changed:
        skill = skill[:summon_start] + summon + skill[summon_end:]
        text = text[:skill_start] + skill + text[skill_end:]
        if not dry_run:
            atomic_write_text(path, text)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    client_changed = patch_client(CLIENT_SKILL, dry_run=args.dry_run, verify=args.verify)
    server_changed = patch_server(SERVER_SKILL, dry_run=args.dry_run, verify=args.verify)
    if args.verify:
        print(f"verified {SKILL_ID} summon origin.x offset: +{X_OFFSET}px")
    elif args.dry_run:
        print(f"[dry-run] client change={client_changed}, server change={server_changed}")
    else:
        print(f"patched {SKILL_ID} summon origin.x offset: +{X_OFFSET}px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Same-length attackCount patch for explorer-warrior MCV ults.

Keep TMS attackCount on visible and hidden nodes. Continuous replay uses
those counts on the existing multiAttackInfo stages.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(ROOT / "tool" / "scripts" / "migration"))

from migrate_arcane_river_expansion import (  # noqa: E402
    atomic_write_bytes,
    atomic_write_text,
    verify_raw_record_scope,
)
from wzpy.crypto import WzKey  # noqa: E402
from wzpy.incremental_img import mutate_img  # noqa: E402
from wzpy.wz_image import WzImage  # noqa: E402

CLIENT_FILES = {
    "112": ROOT / "clien" / "Data" / "Skill" / "112.img",
    "132": ROOT / "clien" / "Data" / "Skill" / "132.img",
}
SERVER_FILES = {
    "112": ROOT / "gms-server" / "wz" / "Skill.wz" / "112.img.xml",
    "132": ROOT / "gms-server" / "wz" / "Skill.wz" / "132.img.xml",
}
# 112: keep current TMS 14/15. 132 visible/hidden keep source
# attackCount (6/14/12/15). Do not collapse to 1-hit 500ms pulses.
ATTACK_COUNTS = {
    "1121023": 14,
    "1121024": 15,
    "1321018": 6,
    "1321019": 14,
    "1321025": 12,
    "1321026": 15,
}


def patch_client(book: str) -> bytes:
    path = CLIENT_FILES[book]
    before = path.read_bytes()
    data = before
    approved = set()
    for skill_id, value in ATTACK_COUNTS.items():
        if not skill_id.startswith(book):
            continue
        for level in range(1, 31):
            prop_path = ("skill", skill_id, "level", str(level), "attackCount")
            approved.add(prop_path)
            result = mutate_img(
                data,
                "edit",
                prop_path,
                values={"value": value},
                region="GMS",
            )
            if result.byte_delta != 0:
                raise SystemExit(
                    f"{'/'.join(prop_path)} length changed by {result.byte_delta}"
                )
            data = result.data
    verify_raw_record_scope(before, data, approved, allow_additions=False)
    image = WzImage.from_bytes(data, key=WzKey.for_region("GMS"))
    image.parse()
    if image.truncated or image.parse_warnings:
        raise SystemExit(image.parse_warnings)
    skill_root = image.root.child("skill")
    for skill_id, value in ATTACK_COUNTS.items():
        if not skill_id.startswith(book):
            continue
        node = skill_root.child(skill_id)
        if node is None:
            raise SystemExit(f"missing {skill_id}")
        for level in range(1, 31):
            actual = int(node.child("level").child(str(level)).child("attackCount").value)
            if actual != value:
                raise SystemExit(f"{skill_id} lv{level} attackCount={actual}")
    return data


def patch_xml(book: str) -> None:
    path = SERVER_FILES[book]
    text = path.read_text(encoding="utf-8")
    for skill_id, value in ATTACK_COUNTS.items():
        if not skill_id.startswith(book):
            continue
        match = re.search(
            rf'(  <imgdir name="{skill_id}">\n.*?\n  </imgdir>\n)',
            text,
            flags=re.S,
        )
        if match is None:
            raise SystemExit(f"xml block {skill_id} not found")
        block = match.group(1)
        updated, count = re.subn(
            r'<int name="attackCount" value="\d+" />',
            f'<int name="attackCount" value="{value}" />',
            block,
        )
        if count != 30:
            raise SystemExit(f"{skill_id} rewrote {count} attackCount nodes")
        text = text[: match.start(1)] + updated + text[match.end(1) :]
    atomic_write_text(path, text)


def main() -> int:
    hashes = {}
    for book in ("132",):
        first = patch_client(book)
        atomic_write_bytes(CLIENT_FILES[book], first)
        digest = hashlib.sha256(first).hexdigest()
        second = patch_client(book)
        if hashlib.sha256(second).hexdigest() != digest:
            raise SystemExit(f"{book}.img not idempotent")
        atomic_write_bytes(CLIENT_FILES[book], second)
        patch_xml(book)
        hashes[book] = digest
        print(f"client {book}.img", digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

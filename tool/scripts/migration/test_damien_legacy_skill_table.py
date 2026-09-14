#!/usr/bin/env python3
"""Contract: Damien boss skill tables use the legacy GMS three-field projection."""

from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_arcane_river_expansion as arc  # noqa: E402
import migrate_demian as demian  # noqa: E402
from wzpy import WzImage  # noqa: E402

PATCH = ROOT / "tool/scripts/migration/patch_damien_legacy_skill_table.py"
SPEC = importlib.util.spec_from_file_location("patch_damien_legacy_skill_table", PATCH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {PATCH}")
patch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patch)


def load_client(mob_id: int) -> WzImage:
    image = WzImage.from_bytes(
        demian.client_mob_path(mob_id).read_bytes(),
        key=arc.GMS_KEY,
        name=f"{mob_id}.img",
    )
    image.parse()
    return image


def xml_skill_rows(mob_id: int) -> list[dict[str, int]]:
    root = ET.parse(demian.server_mob_path("wz", mob_id)).getroot()
    skill = root.find('./imgdir[@name="info"]/imgdir[@name="skill"]')
    if skill is None:
        return []
    rows = []
    for entry in skill.findall("imgdir"):
        row = {}
        for child in entry:
            if child.tag == "int":
                row[child.get("name") or ""] = int(child.get("value") or 0)
        rows.append(row)
    return rows


def main() -> int:
    errors: list[str] = []
    mob_ids = (*demian.BOSS_IDS, *demian.DEPENDENCY_MOBS)
    for mob_id in mob_ids:
        image = load_client(mob_id)
        try:
            patch.assert_legacy_skill_table(mob_id, image)
        except RuntimeError as exc:
            errors.append(str(exc))
        for entry in patch.read_skill_table(image):
            for field in demian.MODERN_SKILL_FIELDS:
                if field in entry:
                    errors.append(f"{mob_id} client kept {field}")
        expected = list(demian.skills_for_mob(mob_id))
        xml_rows = xml_skill_rows(mob_id)
        if xml_rows != expected:
            errors.append(f"{mob_id} server skill table mismatch")
        for row in xml_rows:
            if set(row) != set(demian.LEGACY_SKILL_FIELDS):
                errors.append(f"{mob_id} server kept modern fields: {sorted(row)}")

    if errors:
        print("\n".join(errors))
        return 1
    print("damien legacy skill table contract ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

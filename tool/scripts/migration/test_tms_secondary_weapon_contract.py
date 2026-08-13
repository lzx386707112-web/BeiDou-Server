#!/usr/bin/env python3
"""Contract checks for migrated level-120+ Explorer/Cygnus secondary weapons."""

from __future__ import annotations

import sys
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from migrate_tms_secondary_weapons import (  # noqa: E402
    common,
    EXISTING_RESOURCE_IDS,
    NEW_RESOURCE_IDS,
    SECONDARY_WEAPON_IDS,
    verify_outputs,
)


def git_blob(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def check_client_string_scope() -> None:
    baseline = git_blob(common.CLIENT_STRING)
    current = common.CLIENT_STRING.read_bytes()
    old_image = common.load_image_bytes(baseline, common.CLIENT_STRING.name)
    new_image = common.load_image_bytes(current, common.CLIENT_STRING.name)
    _, _, old_names, old_spans = common.locate_weapon_records(old_image, baseline)
    _, _, new_names, new_spans = common.locate_weapon_records(new_image, current)
    allowed = set(str(item_id) for item_id in NEW_RESOURCE_IDS)
    added = set(new_names) - set(old_names)
    assert allowed <= added
    old_raw = {name: baseline[a:b] for name, (a, b) in zip(old_names, old_spans)}
    new_raw = {name: current[a:b] for name, (a, b) in zip(new_names, new_spans)}
    for name in old_names:
        assert old_raw[name] == new_raw[name], f"existing Weapon string changed: {name}"


def main() -> None:
    assert len(SECONDARY_WEAPON_IDS) == 26
    assert len(NEW_RESOURCE_IDS) == 24
    assert EXISTING_RESOURCE_IDS == (1352206, 1352216)
    assert all(item_id // 10000 == 135 for item_id in SECONDARY_WEAPON_IDS)
    check_client_string_scope()
    verify_outputs()
    print("secondary-weapon migration contract passed: 26 selected, 24 added, 2 preserved")


if __name__ == "__main__":
    main()

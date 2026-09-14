#!/usr/bin/env python3
"""Contract: Damien skill1 has no hide overlays and uses a single Hard-Skin slot."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python"), str(Path(__file__).resolve().parent)]

import migrate_demian as demian  # noqa: E402

PATCH = ROOT / "tool/scripts/migration/patch_damien_hit_compat.py"
SPEC = importlib.util.spec_from_file_location("patch_damien_hit_compat", PATCH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {PATCH}")
patch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(patch)


def main() -> int:
    errors: list[str] = []
    for mob_id in (*demian.BOSS_IDS, *demian.DEPENDENCY_MOBS):
        image = patch.load_client(demian.client_mob_path(mob_id))
        try:
            patch.assert_hit_compat(mob_id, image)
        except RuntimeError as exc:
            errors.append(str(exc))
        if list(demian.skills_for_mob(mob_id)) != [{"skill": 142, "action": 1, "level": 1}]:
            errors.append(f"{mob_id} expected a single skill1 slot")
    if errors:
        print("\n".join(errors))
        return 1
    print("damien hit-compat contract ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

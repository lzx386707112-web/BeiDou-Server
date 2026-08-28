#!/usr/bin/env python3
"""Contract checks for the Arcana 450005220 obj/7 repair."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/scripts/patch-client"))

import repair_arcana_450005220_obj7 as repair  # noqa: E402


def main() -> int:
    expected = repair.build_expected()
    for path, (baseline, result) in expected.items():
        assert path.read_bytes() == result
        if path == repair.CLIENT:
            repair.arc.verify_raw_record_insert_scope(
                baseline,
                result,
                {(*repair.PARENT_PATH, repair.INSERT_NAME)},
            )

    node = repair.projected_node()
    assert repair.client_state(repair.CLIENT.read_bytes(), node) == "repaired"
    assert repair.server_state(repair.SERVER.read_text(encoding="utf-8"), node) == "repaired"
    repair.validate_resource_canvas()
    print(
        "Arcana 450005220 obj contract ok: 1/obj/7 restored; "
        "numbering=0..19; client/server synchronized; canvas visible"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

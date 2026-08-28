#!/usr/bin/env python3
"""Contract checks for the Arcana 450005242 object-gap repair."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/scripts/patch-client"))

import repair_arcana_450005242_obj_gaps as repair  # noqa: E402


def main() -> int:
    expected = repair.build_expected()
    for path, (baseline, result) in expected.items():
        assert path.read_bytes() == result
        if path == repair.CLIENT and baseline != result:
            repair.arc.verify_raw_record_insert_scope(
                baseline,
                result,
                {(*repair.PARENT_PATH, name) for name in repair.INSERT_NAMES},
            )

    nodes = repair.projected_nodes()
    assert repair.client_state(repair.CLIENT.read_bytes(), nodes) == "repaired"
    assert repair.server_state(repair.SERVER.read_text(encoding="utf-8"), nodes) == "repaired"
    repair.validate_resource_canvases()
    print(
        "Arcana 450005242 obj contract ok: 1/obj/3,8 restored; "
        "numbering=0..11; client/server synchronized; canvases visible"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

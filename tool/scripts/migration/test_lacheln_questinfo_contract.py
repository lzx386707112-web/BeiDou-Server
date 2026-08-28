#!/usr/bin/env python3
"""Contract checks for the incremental Lacheln client quest repair."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/scripts/patch-client"))

import repair_lacheln_quest_data as repair  # noqa: E402


def main() -> int:
    expected = repair.build_expected()
    assert len(repair.INSERT_IDS) == 27
    for path, (_baseline, result) in expected.items():
        assert path.read_bytes() == result
    print(
        "Lacheln client quest contract ok: Act/Check/Say +27 positive records; "
        "QuestInfo preserved; signed client roots=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

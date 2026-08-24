#!/usr/bin/env python3
"""Contract checks for the incremental Lacheln QuestInfo repair."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/scripts/patch-client"))

import repair_lacheln_questinfo as repair  # noqa: E402


def main() -> int:
    expected, insert_names = repair.build_expected()
    actual = repair.TARGET.read_bytes()
    assert actual == expected
    assert len(insert_names) == 27
    repair.verify_expected(repair.BASELINE.read_bytes(), actual, insert_names)
    print(
        "Lacheln QuestInfo contract ok: clean baseline + 27 positive 343xx records; "
        "signed Chu Chu duplicates=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = (
    ROOT / "gms-server/src/main/resources/db/migration/"
    "V2.1.54__remove_dark_lords_secret_scroll.sql"
)


class RetiredNightLordSkillsContractTest(unittest.TestCase):
    def test_dark_lords_secret_scroll_persistence_is_removed(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        self.assertEqual(6, len(re.findall(r"\b4121012\b", sql)))
        for table in ("cooldowns", "keymap", "skillmacros", "skills"):
            self.assertIn(f"DELETE FROM `{table}`", sql)


if __name__ == "__main__":
    unittest.main()

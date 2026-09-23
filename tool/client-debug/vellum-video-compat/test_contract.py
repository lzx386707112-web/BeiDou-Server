#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).with_name("VellumVideoCompat.cpp")
WRAPPER = ROOT / "tool/client-debug/dawn-warrior-skill-compat/HpMpExpansionWrapper.cpp"
CORE = ROOT / "clien/BeiDouSkillCompatCore.dll"
VERIFIED_CORE_SHA256 = "3882737456d7c95795b2afe63ad91703cd70ef299c6b83fefe5f6f70764b466f"


class VellumVideoCompatContract(unittest.TestCase):
    def test_only_new_vellum_screens_are_mapped(self) -> None:
        source = SOURCE.read_text()
        self.assertIn("kAttack10MarkerCode = 5", source)
        self.assertIn("kAttack11MarkerCode = 6", source)
        self.assertIn("root-abyss-vellum-attack10.mcv", source)
        self.assertIn("root-abyss-vellum-attack11.mcv", source)
        for old_name in ("pierre.mcv", "vonbon.mcv", "queen.mcv", "root-abyss-vellum.mcv"):
            self.assertNotIn(old_name, source)

    def test_extension_chains_after_verified_core(self) -> None:
        source = SOURCE.read_text()
        self.assertIn("CoreHooksAreReady(core)", source)
        self.assertIn("PointerBelongsToModule(*slot, core)", source)
        wrapper = WRAPPER.read_text()
        self.assertLess(
            wrapper.index("LoadSiblingDll(kCoreDllName)"),
            wrapper.index("LoadSiblingDll(kVellumVideoDllName)"),
        )

    def test_verified_core_is_unchanged(self) -> None:
        self.assertEqual(hashlib.sha256(CORE.read_bytes()).hexdigest(), VERIFIED_CORE_SHA256)


if __name__ == "__main__":
    unittest.main()

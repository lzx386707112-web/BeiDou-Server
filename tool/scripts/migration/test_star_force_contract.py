from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "gms-server/scripts-zh-CN/BeiDouSpecial/装备制作/星级强化.js"
SOURCE = SCRIPT.read_text(encoding="utf-8")


class StarForceContractTest(unittest.TestCase):
    def require(self, fragment: str) -> None:
        self.assertIn(fragment, SOURCE, f"missing star-force contract: {fragment}")

    def test_weapon_slot_and_scroll_requirements(self) -> None:
        self.require("getInventory(InventoryType.EQUIP).getItem(1)")
        self.require("itemId >= 1302000 && itemId < 1493000")
        self.require("item.getUpgradeSlots() !== 0")
        self.require("matchesSelectedItem(item)")

    def test_level_capacity_boundaries(self) -> None:
        for fragment in (
            "if (requiredLevel <= 94) return 5;",
            "if (requiredLevel <= 107) return 8;",
            "if (requiredLevel <= 117) return 10;",
            "if (requiredLevel <= 127) return 15;",
            "if (requiredLevel <= 137) return 20;",
            "return 25;",
        ):
            self.require(fragment)
        self.require("getEquipLevelReq(itemId)")

    def test_exact_probability_table(self) -> None:
        entries = re.findall(
            r"\{success: (\d+), failure: (\d+), destroy: (\d+)\}", SOURCE
        )
        expected = [
            (9500, 500, 0), (9000, 1000, 0), (8500, 1500, 0),
            (8500, 1500, 0), (8000, 2000, 0), (7500, 2500, 0),
            (7000, 3000, 0), (6500, 3500, 0), (6000, 4000, 0),
            (5500, 4500, 0), (5000, 5000, 0), (4500, 5500, 0),
            (4000, 6000, 0), (3500, 6500, 0), (3000, 7000, 0),
            (3000, 7000, 0), (3000, 7000, 0), (1500, 7820, 680),
            (1500, 7820, 680), (1500, 7650, 850), (3000, 5950, 1050),
            (1500, 7225, 1275), (1500, 6800, 1700),
            (1000, 7200, 1800), (1000, 7200, 1800),
        ]
        self.assertEqual([tuple(map(int, row)) for row in entries], expected)
        self.assertTrue(all(sum(row) == 10000 for row in expected))

    def test_pity_safeguard_and_failure_rules(self) -> None:
        self.require("if (consecutiveFailures >= 5) return SUCCESS;")
        self.require("return currentStar === 17;")
        self.require("getMesoCost(requiredLevel, currentStar) * (mesoSafeguard ? 2 : 1)")
        self.require("if (result === DESTROYED && mesoSafeguard) result = FAILURE;")
        self.require("var SAFE_CHECKPOINTS = {10: true, 15: true, 20: true};")
        self.require("if (currentStar < 17 || SAFE_CHECKPOINTS[currentStar])")

    def test_safeguard_scroll_contract(self) -> None:
        expected = {
            4260012: 200,
            4260013: 400,
            4260014: 600,
            4260015: 800,
            4260016: 1000,
            4260017: 1200,
            4260018: 1400,
            4260019: 1600,
        }
        entries = re.findall(r"(426001[2-9]): (\d+)", SOURCE)
        self.assertEqual({int(item): int(rate) for item, rate in entries}, expected)
        self.require("getInventory(InventoryType.ETC).getItem(2)")
        self.require("cm.getClient(), InventoryType.ETC, 2, 1, false")
        self.require("STAR_RATES[currentStar].destroy - reduction")
        self.require("if (roll < 10000 - adjustedDestroy) return FAILURE;")

    def test_meso_formula(self) -> None:
        self.require("Math.pow(requiredLevel, 3)")
        self.require("levelCubed * (currentStar + 1) / 25")
        self.require("Math.pow(currentStar + 1, 2.7) / 400")
        self.require("Math.pow(currentStar + 1, 2.7) / 200")
        self.require("Math.max(1000, Math.round(rawCost / 1000) * 1000)")

    def test_stat_rules(self) -> None:
        self.require("targetStar <= 5 ? 2 : 3")
        self.require("Math.floor(item.getWatk() / 50) + 1")
        self.require("Math.floor(item.getMatk() / 50) + 1")
        for fragment in (
            "{main: 7, attack: targetStar - 9}",
            "{main: 9, attack: targetStar - 8}",
            "{main: 11, attack: targetStar - 7}",
            "{main: 13, attack: targetStar - 6}",
            "{main: 15, attack: targetStar - 4}",
        ):
            self.require(fragment)
        self.require("[130, 131, 132, 140, 141, 142, 143, 144, 148]")
        self.require("[133, 134, 136, 147]")
        self.require("[137, 138]")
        self.require("[145, 146, 149]")
        self.require("removeStarStats(item, currentStar, requiredLevel)")

    def test_outcomes_are_persisted(self) -> None:
        self.require("item.setStarLevel(targetStar);")
        self.require("item.setStarCount(0);")
        self.require("item.setStarCount(item.getStarCount() + 1);")
        self.require("item.setMaxStar(maxStar);")
        self.require('item.setOwner(item.getStarLevel() + "★");')
        self.require("cm.getPlayer().forceUpdateItem(item);")
        self.require("InventoryManipulator.removeFromSlot(")
        self.require("cm.getClient(), InventoryType.EQUIP, 1, 1, false")

    def test_old_material_system_is_removed(self) -> None:
        for obsolete in ("needItems", "cash_id", "exp_id", "升级装备白名单", "maxStarLevel = 50"):
            self.assertNotIn(obsolete, SOURCE)


if __name__ == "__main__":
    unittest.main()

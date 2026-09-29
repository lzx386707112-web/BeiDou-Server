#!/usr/bin/env python3
"""Post-migration contract for the Root Abyss and Fallen World Tree removal."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

import remove_root_abyss_world_tree as migration  # noqa: E402
from wzpy.incremental_img import _find_record, scan_img  # noqa: E402
from wzpy.incremental_xml import _find_node, scan_xml  # noqa: E402
from wzpy.wz_image import WzImage  # noqa: E402
from wzpy.crypto import WzKey  # noqa: E402


def img_has(path: Path, record_path: tuple[str, ...]) -> bool:
    try:
        _find_record(scan_img(path.read_bytes()).root, record_path)
        return True
    except KeyError:
        return False


def xml_has(path: Path, record_path: tuple[str, ...]) -> bool:
    try:
        _find_node(scan_xml(path.read_text(encoding="utf-8")), record_path)
        return True
    except KeyError:
        return False


def client_shared_targets() -> dict[Path, list[tuple[str, ...]]]:
    targets = {
        ROOT / "clien/Data/String/Map.img": [("victoria", str(value)) for value in migration.MAP_STRING_IDS],
        ROOT / "clien/Data/String/Mob.img": [(str(value),) for value in migration.MOB_STRING_IDS],
        ROOT / "clien/Data/String/Npc.img": [(str(value),) for value in migration.NPC_STRING_IDS],
        ROOT / "clien/Data/Skill/MobSkill.img": list(migration.CLIENT_MOB_SKILLS),
        ROOT / "clien/Data/Sound/Mob.img": [("8900000",)],
        ROOT / "clien/Data/UI/UIWindow.img": [
            ("MobGage", "Mob", str(value))
            for value in migration.DIRECT_MOB_GAUGE_IDS + migration.ALIAS_MOB_GAUGE_IDS
        ],
        ROOT / "clien/Data/Map/Map/Map1/105040300.img": [("portal", "24")],
        ROOT / "clien/Data/Map/Map/Map9/951000000.img": [("life", "5"), ("portal", "5")],
        ROOT / "clien/Data/Map/Obj/effect.img": [("quest", "gate", "8")],
        ROOT / "clien/Data/Map/Obj/gran_helisium.img": [("citadel_boss", "magnus", "14")],
        ROOT / "clien/Data/Map/Obj/house.img": [("fallenWorldTree",)],
        ROOT / "clien/Data/Map/Effect.img": [("customSkill", "rootAbyss"), ("customBossDemian",)],
    }
    targets[ROOT / "clien/Data/String/Map.img"].extend(
        [("etc", str(value)) for value in migration.MONSTER_PARK_MAPS]
    )
    targets[ROOT / "clien/Data/String/Mob.img"].extend(
        [(str(value),) for value in migration.MONSTER_PARK_MOB_IDS]
    )
    targets[ROOT / "clien/Data/String/Npc.img"].extend(
        [(str(value),) for value in migration.MONSTER_PARK_NPC_IDS]
    )
    for name in ("Act", "Check", "QuestInfo", "Say"):
        targets[ROOT / "clien/Data/Quest" / f"{name}.img"] = [
            (str(value),) for value in migration.QUEST_CLIENT_IDS
        ]
    return targets


class RemovedRegionContract(unittest.TestCase):
    def test_exclusive_runtime_files_are_absent(self) -> None:
        for path in migration.paired_resource_files():
            self.assertFalse(path.exists(), path)
        for path in migration.independent_resource_files():
            self.assertFalse(path.exists(), path)
        for path in migration.script_files():
            self.assertFalse(path.exists(), path)
        for path in migration.monster_park_paired_resource_files():
            self.assertFalse(path.exists(), path)
        for path in migration.monster_park_exclusive_resource_files():
            self.assertFalse(path.exists(), path)
        for path in migration.monster_park_script_files():
            self.assertFalse(path.exists(), path)

    def test_client_shared_records_are_absent(self) -> None:
        for path, records in client_shared_targets().items():
            image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region(scan_img(path.read_bytes()).region))
            image.parse()
            self.assertFalse(image.truncated, path)
            self.assertEqual([], image.parse_warnings, path)
            for record in records:
                self.assertFalse(img_has(path, record), f"{path}:{'/'.join(record)}")

    def test_remaining_client_records_match_git_baseline(self) -> None:
        def compare_lists(base_data, base_list, current_data, current_list, prefix, removed):
            expected = [record for record in base_list.records if prefix + (record.name,) not in removed]
            self.assertEqual(
                [record.name for record in expected],
                [record.name for record in current_list.records],
                "/".join(prefix),
            )
            for base_record, current_record in zip(expected, current_list.records):
                path = prefix + (base_record.name,)
                is_ancestor = any(target[:len(path)] == path for target in removed)
                if is_ancestor:
                    self.assertIsNotNone(base_record.children, path)
                    self.assertIsNotNone(current_record.children, path)
                    compare_lists(
                        base_data,
                        base_record.children,
                        current_data,
                        current_record.children,
                        path,
                        removed,
                    )
                else:
                    self.assertEqual(
                        base_data[base_record.start:base_record.end],
                        current_data[current_record.start:current_record.end],
                        "/".join(path),
                    )

        for path, records in client_shared_targets().items():
            relative = path.relative_to(ROOT).as_posix()
            baseline = subprocess.check_output(["git", "cat-file", "blob", f"HEAD:{relative}"], cwd=ROOT)
            current = path.read_bytes()
            compare_lists(
                baseline,
                scan_img(baseline).root,
                current,
                scan_img(current).root,
                (),
                set(records),
            )

    def test_server_shared_records_are_absent(self) -> None:
        xml_targets = {
            ROOT / "gms-server/wz/String.wz/Map.img.xml": [("victoria", str(value)) for value in migration.MAP_STRING_IDS],
            ROOT / "gms-server/wz/String.wz/Mob.img.xml": [(str(value),) for value in migration.MOB_STRING_IDS],
            ROOT / "gms-server/wz/String.wz/Npc.img.xml": [(str(value),) for value in migration.NPC_STRING_IDS],
            ROOT / "gms-server/wz/Skill.wz/MobSkill.img.xml": list(migration.SERVER_MOB_SKILLS),
            ROOT / "gms-server/wz/Sound.wz/Mob.img.xml": [("8900000",)],
            ROOT / "gms-server/wz/UI.wz/UIWindow.img.xml": [
                ("MobGage", "Mob", str(value))
                for value in migration.DIRECT_MOB_GAUGE_IDS + migration.ALIAS_MOB_GAUGE_IDS
            ],
            ROOT / "gms-server/wz/Map.wz/Map/Map1/105040300.img.xml": [("portal", "24")],
            ROOT / "gms-server/wz/Map.wz/Map/Map9/951000000.img.xml": [("life", "5"), ("portal", "5")],
            ROOT / "gms-server/wz/Map.wz/Obj/effect.img.xml": [("quest", "gate", "8")],
            ROOT / "gms-server/wz/Map.wz/Obj/gran_helisium.img.xml": [("citadel_boss", "magnus", "14")],
        }
        xml_targets[ROOT / "gms-server/wz/String.wz/Map.img.xml"].extend(
            [("etc", str(value)) for value in migration.MONSTER_PARK_MAPS]
        )
        xml_targets[ROOT / "gms-server/wz/String.wz/Mob.img.xml"].extend(
            [(str(value),) for value in migration.MONSTER_PARK_MOB_IDS]
        )
        xml_targets[ROOT / "gms-server/wz/String.wz/Npc.img.xml"].extend(
            [(str(value),) for value in migration.MONSTER_PARK_NPC_IDS]
        )
        for tree in ("wz", "wz-zh-CN"):
            for name in ("Act", "Check", "QuestInfo", "Say"):
                xml_targets[ROOT / "gms-server" / tree / "Quest.wz" / f"{name}.img.xml"] = [
                    (str(value),) for value in migration.QUEST_SERVER_IDS
                ]
        for path, records in xml_targets.items():
            for record in records:
                self.assertFalse(xml_has(path, record), f"{path}:{'/'.join(record)}")

    def test_similar_ids_and_shared_skills_are_preserved(self) -> None:
        protected_files = (
            ROOT / "clien/Data/Map/Map/Map9/910520000.img",
            ROOT / "clien/Data/Npc/1052000.img",
            ROOT / "gms-server/scripts-zh-CN/map/onUserEnter/954105200.js",
            ROOT / "gms-server/scripts-zh-CN/map/onUserEnter/954105300.js",
        )
        for path in protected_files:
            self.assertTrue(path.exists(), path)
        mob_skill = ROOT / "clien/Data/Skill/MobSkill.img"
        self.assertFalse(img_has(mob_skill, ("186",)))
        for record in (("183", "level", "1"), ("184", "level", "1")):
            self.assertTrue(img_has(mob_skill, record), record)

    def test_admin_mob_catalog_has_no_deleted_mobs(self) -> None:
        path = ROOT / "gms-server/src/main/resources/mob-catalog/catalog.json"
        catalog = json.loads(path.read_text(encoding="utf-8"))
        remaining = {int(mob["id"]) for mob in catalog["mobs"]}
        self.assertTrue(remaining.isdisjoint(migration.MOB_IDS + migration.MONSTER_PARK_MOB_IDS))
        self.assertEqual(len(catalog["mobs"]), int(catalog["atlas"]["count"]))
        self.assertEqual(sum(bool(mob.get("icon")) for mob in catalog["mobs"]), int(catalog["atlas"]["icons"]))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Static contracts for indexed DAMAGE_MONSTER and sword-illusion local 0xBA numbers."""

from pathlib import Path
import re
import unittest


SOURCE = Path(__file__).with_name("IndexedDamageNumberCompat.cpp")
ROOT = SOURCE.resolve().parents[3]


def parse_byte_array(source: str, name: str) -> bytes:
    match = re.search(rf"{name}\[\] = \{{(?P<body>.*?)\}};", source, re.DOTALL)
    if match is None:
        raise AssertionError(f"missing {name}")
    return bytes(int(value, 16) for value in re.findall(r"0x([0-9A-F]{2})", match.group("body")))


class IndexedDamageNumberContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SOURCE.read_text(encoding="utf-8")
        self.executable = (ROOT / "clien/BeiDou.exe").read_bytes()

    def test_damage_monster_hook_bytes_match_client(self) -> None:
        expected = parse_byte_array(self.source, "kDamageMonsterOriginal")
        self.assertEqual(30, len(expected))
        self.assertEqual(expected, self.executable[0x26C6CB : 0x26C6CB + 30])
        self.assertIn("Indexed Damage Number Compat v3", self.source)

    def test_sword_illusion_lookup_bytes_match_client(self) -> None:
        expected = parse_byte_array(self.source, "kLocalAttackLookupOriginal")
        self.assertEqual(expected, self.executable[0x572512 : 0x572512 + len(expected)])
        self.assertIn("0x00111AFD", self.source)
        self.assertIn("0x00111AFE", self.source)
        self.assertNotIn("0x00111B00", self.source)
        self.assertNotIn("0x0012A19D", self.source)
        self.assertNotIn("0x0012A19E", self.source)
        self.assertNotIn("0x0012A1A7", self.source)
        self.assertNotIn("0x0014283B", self.source)
        self.assertNotIn("0x00142842", self.source)
        self.assertIn("0x0097251A", self.source)
        self.assertIn("0x00972626", self.source)

    def test_spirit_caliber_server_uses_cosmos_style_numbers(self) -> None:
        close_handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ).read_text(encoding="utf-8")
        block = close_handler[
            close_handler.index("chr.sendPacket(PacketCreator.showEffect(SPIRIT_CALIBER_VIDEO_LAYER));") :
            close_handler.index("} else if (attack.skill == Hero.RAGE_UPRISING_VI)")
        ]
        self.assertIn("SPIRIT_CALIBER_TIMES_MS", block)
        self.assertIn("SPIRIT_CALIBER_FINISH_TIMES_MS", block)
        self.assertIn("SPIRIT_CALIBER_FINISH, true", block)
        self.assertIn("SPIRIT_CALIBER_FINISH, false", block)
        self.assertEqual(2, block.count("LocalDamageNumberMode.INDEXED"))
        self.assertNotIn("LocalDamageNumberMode.TOTAL", block)
        self.assertNotIn("damageMonster(", block)
        self.assertNotIn("FULLSCREEN_MCV_ATTACK_INTERVAL_MS", close_handler)
        self.assertNotIn("collectFullMapCloseTargets(", close_handler)
        self.assertIn(
            "840, 900, 960, 1020, 1080, 1140, 1200, 1260, 1320, 1380, 1440,",
            close_handler,
        )

    def test_dead_space_server_uses_cosmos_style_numbers(self) -> None:
        close_handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ).read_text(encoding="utf-8")
        block = close_handler[
            close_handler.index("chr.sendPacket(PacketCreator.showEffect(DEAD_SPACE_VIDEO_LAYER));") :
            close_handler.index("} else if (attack.skill == DarkKnight.DARK_HALIDOM)")
        ]
        self.assertIn("DEAD_SPACE_TIMES_MS", block)
        self.assertIn("DEAD_SPACE_FINISH_TIMES_MS", block)
        self.assertIn("DEAD_SPACE_FINISH, true", block)
        self.assertIn("DEAD_SPACE_FINISH, false", block)
        self.assertEqual(2, block.count("LocalDamageNumberMode.INDEXED"))
        self.assertNotIn("LocalDamageNumberMode.TOTAL", block)
        self.assertNotIn("damageMonster(", block)
        self.assertIn(
            "private static final int[] DEAD_SPACE_TIMES_MS = {60, 120, 180, 240, 300, 360};",
            close_handler,
        )
        self.assertNotIn("replayAttackCount = 1;", close_handler)
        self.assertIn("originalEffect.applyTo(chr);", close_handler)

    def test_dark_halidom_server_uses_cosmos_style_numbers(self) -> None:
        close_handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ).read_text(encoding="utf-8")
        block = close_handler[
            close_handler.index("chr.sendPacket(PacketCreator.showEffect(DARK_HALIDOM_VIDEO_LAYER));") :
            close_handler.index("} else if (attack.skill == DawnWarrior.GALAXY_STAR_BURST)")
        ]
        self.assertIn("DARK_HALIDOM_TIMES_MS", block)
        self.assertIn("DARK_HALIDOM_FINISH_TIMES_MS", block)
        self.assertIn("DARK_HALIDOM_FINISH, true", block)
        self.assertIn("DARK_HALIDOM_FINISH, false", block)
        self.assertEqual(2, block.count("LocalDamageNumberMode.INDEXED"))
        self.assertNotIn("LocalDamageNumberMode.TOTAL", block)
        self.assertNotIn("damageMonster(", block)
        self.assertIn(
            "960, 1020, 1080, 1140, 1200, 1260, 1320, 1380, 1440, 1500, 1560, 1620",
            close_handler,
        )
        self.assertNotIn("DARK_HALIDOM_PULSE_HIT_COUNT", close_handler)

    def test_mcv_wz_attack_count_matches_replay_contract(self) -> None:
        expected = {
            "1121023": 14,
            "1121024": 15,
            "1321018": 6,
            "1321019": 14,
            "1321025": 12,
            "1321026": 15,
        }
        xml_files = {
            "112": ROOT / "gms-server/wz/Skill.wz/112.img.xml",
            "132": ROOT / "gms-server/wz/Skill.wz/132.img.xml",
        }
        for skill_id, value in expected.items():
            book = skill_id[:3]
            text = xml_files[book].read_text(encoding="utf-8")
            match = re.search(
                rf'  <imgdir name="{skill_id}">\n.*?\n  </imgdir>\n',
                text,
                flags=re.S,
            )
            self.assertIsNotNone(match, skill_id)
            counts = re.findall(
                r'<int name="attackCount" value="(\d+)" />',
                match.group(0),
            )
            self.assertEqual(30, len(counts), skill_id)
            self.assertTrue(all(int(item) == value for item in counts), skill_id)

    def test_local_action_skips_match_client(self) -> None:
        move = parse_byte_array(self.source, "kSkipLocalMoveOriginal")
        attack_byte = parse_byte_array(self.source, "kSkipLocalAttackByteOriginal")
        self.assertEqual(move, self.executable[0x58046E : 0x58046E + len(move)])
        self.assertEqual(
            attack_byte,
            self.executable[0x5803E5 : 0x5803E5 + len(attack_byte)],
        )
        self.assertIn("0x009804BB", self.source)
        self.assertIn("0x00980477", self.source)
        self.assertIn("0x009803EB", self.source)

    def test_hook_does_not_call_remote_attack_entry(self) -> None:
        self.assertNotIn("mov eax, 0x009803AB", self.source)
        self.assertIn("0x0066B05E", self.source)
        self.assertIn("0x006691D3", self.source)

    def test_magic_and_ranged_mcv_replays_use_indexed_numbers(self) -> None:
        magic_handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/MagicDamageHandler.java"
        ).read_text(encoding="utf-8")
        ranged_handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/RangedAttackHandler.java"
        ).read_text(encoding="utf-8")

        self.assertIn("explorerVideoLayer != null", magic_handler)
        self.assertIn(
            "if (ExplorerOtherSkillCompat.multiAttacks(attack.skill) == null)",
            magic_handler,
        )
        self.assertIn("showIndexedDamageNumbers(chr, expectedMap, damage);", magic_handler)
        for marker in (
            "BlazeWizard.ETERNAL_PHOENIX_BURST, true, true",
            "BlazeWizard.ETERNAL_PHOENIX_CYCLE, false, true",
            "BlazeWizard.FLAME_CONCERTO_MAIN, true, true",
            "BlazeWizard.FLAME_CONCERTO_FINISH, false, true",
        ):
            self.assertIn(marker, magic_handler)

        self.assertIn("explorerVideoLayer != null", ranged_handler)
        self.assertIn(
            "if (ExplorerOtherSkillCompat.multiAttacks(attack.skill) == null)",
            ranged_handler,
        )
        self.assertIn("showIndexedDamageNumbers(chr, expectedMap, damage);", ranged_handler)
        for marker in (
            "NightWalker.DOMINION_VI_TICK, true",
            "NightWalker.SILENT_NIGHT_DART, true",
            "NightWalker.STYGIAN_COMMAND_MAIN, true",
            "showIndexedDamageNumbers(chr, chr.getMap(), attack.allDamage);",
            "WindArcher.MISTRAL_WIND_BLADE, true",
            "WindArcher.ELEMENTAL_TEMPEST_WAVE, true",
            "damage,\n                    true",
        ):
            self.assertIn(marker, ranged_handler)

    def test_all_explicit_close_range_mcv_branches_use_indexed_numbers(self) -> None:
        close_handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ).read_text(encoding="utf-8")
        branches = (
            ("SPIRIT_CALIBER_VIDEO_LAYER", "Hero.RAGE_UPRISING_VI", 2),
            ("SACRED_BASTION_VIDEO_LAYER", "Paladin.HEAVENS_HAMMER_VI", 3),
            ("DOMINUS_OBRION_VIDEO_LAYER", "DarkKnight.CALAMITOUS_CYCLONE", 2),
            ("DEAD_SPACE_VIDEO_LAYER", "DarkKnight.DARK_HALIDOM", 2),
            ("DARK_HALIDOM_VIDEO_LAYER", "DawnWarrior.GALAXY_STAR_BURST", 2),
            ("GALAXY_STAR_BURST_VIDEO_LAYER", "DawnWarrior.ECLIPSE_FORCE", 1),
            ("ECLIPSE_FORCE_VIDEO_LAYER", "DawnWarrior.SOUL_ECLIPSE", 1),
            ("SOUL_ECLIPSE_VIDEO_LAYER", "DawnWarrior.COSMOS", 1),
            ("WAVE_RIDING_THUNDER_VIDEO_LAYER", "ThunderBreaker.SWIFT_ANNIHILATION", 2),
            ("SWIFT_ANNIHILATION_VIDEO_LAYER", "} else {", 2),
        )
        for start_marker, end_marker, count in branches:
            start = close_handler.index(
                f"chr.sendPacket(PacketCreator.showEffect({start_marker}));"
            )
            end = close_handler.index(end_marker, start)
            self.assertEqual(
                count,
                close_handler[start:end].count("LocalDamageNumberMode.INDEXED"),
                start_marker,
            )
        god_of_sea_start = close_handler.index(
            "chr.sendPacket(PacketCreator.showEffect(GOD_OF_THE_SEA_VI_VIDEO_LAYER));"
        )
        god_of_sea_end = close_handler.index("ThunderBreaker.WAVE_RIDING_THUNDER", god_of_sea_start)
        self.assertIn(
            "showCapturedIndexedDamageNumbers",
            close_handler[god_of_sea_start:god_of_sea_end],
        )

    def test_sword_illusion_server_does_not_use_f6_supplement(self) -> None:
        close_handler = (
            ROOT
            / "gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java"
        ).read_text(encoding="utf-8")
        block = close_handler[
            close_handler.index("} else if (attack.skill == Hero.SWORD_ILLUSION)") :
            close_handler.index("} else if (attack.skill == Hero.DEATH_FAULT)")
        ]
        self.assertIn("SWORD_ILLUSION_SLASH", block)
        self.assertIn("SWORD_ILLUSION_EXPLOSION", block)
        self.assertNotIn("LocalDamageNumberMode.INDEXED", block)
        self.assertNotIn("LocalDamageNumberMode.TOTAL", block)


if __name__ == "__main__":
    unittest.main()

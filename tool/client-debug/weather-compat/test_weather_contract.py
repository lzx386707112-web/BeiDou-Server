#!/usr/bin/env python3

import re
import hashlib
import struct
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


class WeatherCompatContract(unittest.TestCase):
    HOOK_BYTES = {
        0x009F84D0: "b83a82ae00",
        0x00639B3D: "b8c2d2a900",
        0x006399EF: "b8b8d1a900",
        0x0063A100: "b883d3a900",
        0x0063AA7E: "b8acd4a900",
        0x0063CBBA: "b85cd9a900",
        0x0063CD4E: "b8f5dba900",
        0x0063AD16: "b8bfd7a900",
        0x006D9993: "558bec83ec",
        0x00426C7E: "558bec5153",
        0x006406F3: "8d44029c89",
    }

    def test_wire_ids_and_packet_bridge(self):
        entry = (HERE / "src/WeatherCompat.cpp").read_text(encoding="utf-8")
        set_item = (ROOT / "tool/client-debug/set-item-compat/BeiDouSetItemCompat.cpp").read_text(encoding="utf-8")
        server = (ROOT / "gms-server/src/main/java/org/gms/net/opcodes/SendOpcode.java").read_text(encoding="utf-8")
        self.assertIn("0x373D", entry)
        self.assertIn("WEATHER_SYNC(0x373D)", server)
        self.assertIn("BDS_RegisterPacketHandler", entry)
        self.assertIn("BDS_RegisterPacketHandler", set_item)
        self.assertNotIn("0x004965F1", entry)

    def test_profile_and_palette_cardinality(self):
        profiles = (HERE / "src/weather_profiles.inc").read_text(encoding="utf-8")
        palettes = (HERE / "src/weather_palettes.inc").read_text(encoding="utf-8")
        self.assertEqual(9, len(re.findall(r"/\*\s*\d+\s*\*/\s*\{", profiles)))
        self.assertEqual(27, len(re.findall(r"/\*\s*\d+\s*\*/\s*\{", palettes)))

    def test_weather_only_target(self):
        cmake = (HERE / "CMakeLists.txt").read_text(encoding="utf-8")
        for excluded in ("bypass.cpp", "resolution.cpp", "resman.cpp", "injector.cpp",
                         "weathermove.cpp"):
            self.assertNotIn(f"src/{excluded}", cmake)
        entry = (HERE / "src/WeatherCompat.cpp").read_text(encoding="utf-8")
        self.assertNotIn("WeatherMove_", entry)
        self.assertIn("-A Win32", (HERE / "build.ps1").read_text(encoding="utf-8"))

    def test_every_owned_hook_matches_verified_executable(self):
        executable = ROOT / "clien/BeiDou.exe"
        data = executable.read_bytes()
        self.assertEqual(
            "06cdac314a6c91f3e133778aa7b72a829778549d4f14e3b95c3589fed541ba18",
            hashlib.sha256(data).hexdigest(),
        )
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        section_count = struct.unpack_from("<H", data, pe + 6)[0]
        optional_size = struct.unpack_from("<H", data, pe + 20)[0]
        optional = pe + 24
        image_base = struct.unpack_from("<I", data, optional + 28)[0]
        section_table = optional + optional_size
        sections = [struct.unpack_from("<8sIIIIIIHHI", data, section_table + i * 40)
                    for i in range(section_count)]
        for address, expected in self.HOOK_BYTES.items():
            relative = address - image_base
            section = next((value for value in sections
                            if value[2] <= relative < value[2] + max(value[1], value[3])), None)
            self.assertIsNotNone(section, hex(address))
            self.assertNotEqual(0, section[9] & 0x20000000, hex(address))
            offset = section[4] + relative - section[2]
            self.assertEqual(expected, data[offset:offset + 5].hex(), hex(address))


if __name__ == "__main__":
    unittest.main()

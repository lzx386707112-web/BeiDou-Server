#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import importlib.util
import struct
import unittest
from pathlib import Path

import pefile


ROOT = Path(__file__).resolve().parents[3]
DLL = ROOT / "clien/ijl15.dll"
SOURCE = Path(__file__).with_name("config_loader.S")
PROBE_SOURCE = Path(__file__).with_name("probe_login.py")
HOOK_RVA = 0x15925
RETURN_RVA = 0x1592C
ORIGINAL_HOOK = bytes.fromhex("56 83 ec 18 89 65 d0")
BASELINE_SECTION_SHA256 = {
    b".text": "784ad824a57173ffe398aac4fd1c0b8f5956a5841136173ecb1aed927a9c9fd8",
    b".rdata": "9fb1403574a1863957629c4646d4f4939ef16d29376fb9e600305964124a14e8",
    b".data": "2610e3596961bff415cd85f4de46ff59c0db78db2e91860e11d47c826651bcf1",
    b".detourc": "c63121c75963baa3f9c71aa2d826f0628fb2dd26b1668fcc5b0bda648dad6d3e",
    b".detourd": "2ec37d0cdd2014311fbb1971c4e8a4cb8e432396a5f9bc63420cf89254cfaa35",
    b".rsrc": "f38bb1d469e21cd272082067155609d21a0348284cc274df71b98f7d9a6ca297",
    b".reloc": "d714295e48e63e35e45c9c21850d97fe517086ea9a35c1714668cde1903fc4c9",
}


class Ijl15ConfigContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = DLL.read_bytes()
        cls.pe = pefile.PE(data=cls.data)
        cls.section = next(
            section
            for section in cls.pe.sections
            if section.Name.rstrip(b"\0") == b".bdcfg"
        )
        cls.payload = cls.section.get_data()[: cls.section.Misc_VirtualSize]

    def test_hook_enters_config_section_and_returns_after_replaced_bytes(self) -> None:
        hook_offset = self.pe.get_offset_from_rva(HOOK_RVA)
        self.assertEqual(0xE9, self.data[hook_offset])
        displacement = struct.unpack_from("<i", self.data, hook_offset + 1)[0]
        self.assertEqual(self.section.VirtualAddress, HOOK_RVA + 5 + displacement)
        self.assertEqual(b"\x90\x90", self.data[hook_offset + 5 : hook_offset + 7])

        trampoline = self.payload.index(bytes.fromhex("56 83 ec 18 89 65 d0 e9"))
        return_marker = trampoline + 7
        return_displacement = struct.unpack_from("<i", self.payload, return_marker + 1)[0]
        self.assertEqual(
            RETURN_RVA,
            self.section.VirtualAddress + return_marker + 5 + return_displacement,
        )

    def test_both_config_keys_are_embedded_in_lowercase(self) -> None:
        self.assertIn(b"config.ini\0", self.payload)
        self.assertIn(b"serverip_address\0", self.payload)
        self.assertIn(b"serverip_port\0", self.payload)
        self.assertNotIn(b"ServerIP_Address\0", self.payload)
        self.assertNotIn(b"serverIP_Port\0", self.payload)

    def test_existing_sections_match_baseline_except_for_hook(self) -> None:
        for section in self.pe.sections:
            name = section.Name.rstrip(b"\0")
            if name == b".bdcfg":
                continue
            contents = bytearray(section.get_data())
            if name == b".text":
                hook_offset = self.pe.get_offset_from_rva(HOOK_RVA) - section.PointerToRawData
                contents[hook_offset : hook_offset + len(ORIGINAL_HOOK)] = ORIGINAL_HOOK
            self.assertEqual(
                BASELINE_SECTION_SHA256[name],
                hashlib.sha256(contents).hexdigest(),
                name,
            )

    def test_loader_targets_verified_network_globals_and_crt_imports(self) -> None:
        source = SOURCE.read_text(encoding="ascii")
        for token in (
            ".equ IAT_STRTOL, 0x2014c",
            ".equ IAT_FCLOSE, 0x20198",
            ".equ IAT_FGETS, 0x2019c",
            ".equ IAT_FOPEN_S, 0x20190",
            ".equ SERVER_PORT, 0x36594",
            ".equ SERVER_ADDRESS, 0x3659c",
            "cmp eax, 65535",
            "cmp edx, 63",
            "cmp al, 'A'",
            "cmp al, 'Z'",
            "add al, 'a' - 'A'",
        ):
            self.assertIn(token, source)

    def test_original_exports_and_partner_dll_name_remain_present(self) -> None:
        exports = [symbol.name for symbol in self.pe.DIRECTORY_ENTRY_EXPORT.symbols]
        self.assertEqual(
            [
                b"NMCO_CallNMFunc",
                b"NMCO_CallNMFunc2",
                b"NMCO_MemoryFree",
                b"ijlErrorStr",
                b"ijlFree",
                b"ijlGetLibVersion",
                b"ijlInit",
                b"ijlRead",
                b"ijlWrite",
            ],
            exports,
        )
        self.assertIn(b"2ijl15.dll\0", self.data)


class LoginProbeContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("probe_login", PROBE_SOURCE)
        assert spec is not None and spec.loader is not None
        cls.probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.probe)

    def test_custom_encryption_round_trip(self) -> None:
        plain = bytearray((index * 37 + 11) & 0xFF for index in range(47))
        encrypted = plain.copy()
        self.probe.custom_encrypt(encrypted)
        self.assertNotEqual(plain, encrypted)
        self.probe.custom_decrypt(encrypted)
        self.assertEqual(plain, encrypted)

    def test_v83_packet_header_uses_swapped_version(self) -> None:
        self.assertEqual(
            bytes.fromhex("29290629"),
            self.probe.packet_header(bytes.fromhex("46727a29"), 83, 47),
        )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Static contract for the Frenzy Totem client slot and cast hooks."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "tool/client-debug/set-item-compat/BeiDouSetItemCompat.cpp"
WRAPPER = ROOT / "tool/client-debug/dawn-warrior-skill-compat/HpMpExpansionWrapper.cpp"
BODY_PART = ROOT / "gms-server/src/main/java/org/gms/client/inventory/BodyPart.java"
EQUIP_SLOT = ROOT / "gms-server/src/main/java/org/gms/constants/inventory/EquipSlot.java"
CORE_DLL = ROOT / "clien/BeiDouSkillCompatCore.dll"
CORE_SHA256 = "3882737456d7c95795b2afe63ad91703cd70ef299c6b83fefe5f6f70764b466f"
CLIENT_EXE = ROOT / "clien/BeiDou.exe"
CLIENT_EXE_SHA256 = "06cdac314a6c91f3e133778aa7b72a829778549d4f14e3b95c3589fed541ba18"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def rva_bytes(data: bytes, rva: int, size: int) -> bytes:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    require(data[pe:pe + 4] == b"PE\0\0", "compatibility core is not PE")
    section_count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    section_table = pe + 24 + optional_size
    for index in range(section_count):
        section = section_table + index * 40
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", data, section + 8
        )
        mapped_size = max(virtual_size, raw_size)
        if virtual_address <= rva and rva + size <= virtual_address + mapped_size:
            offset = raw_offset + rva - virtual_address
            return data[offset:offset + size]
    raise AssertionError(f"core RVA 0x{rva:X} is not mapped")


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    wrapper = WRAPPER.read_text(encoding="utf-8")
    body_part = BODY_PART.read_text(encoding="utf-8")
    equip_slot = EQUIP_SLOT.read_text(encoding="utf-8")
    core = CORE_DLL.read_bytes()
    client = CLIENT_EXE.read_bytes()

    require(hashlib.sha256(core).hexdigest() == CORE_SHA256,
            "compatibility core DLL hash changed")
    require(hashlib.sha256(client).hexdigest() == CLIENT_EXE_SHA256,
            "BeiDou.exe hash changed")
    expected_core_bytes = {
        0x1425: bytes.fromhex("8B 4E 01 81 F9 68 BA E6 00"),
        0x149A: bytes.fromhex("81 FE F4 1A 11 00"),
        0x1B67: bytes.fromhex("55 89 E5 53 8B 45 08"),
        0x1BFB: bytes.fromhex("83 F8 76 74 17"),
        0x1D26: bytes.fromhex("8B 44 24 08 3D 70 7B 19 00"),
        0x2015: bytes.fromhex("55 89 E5 57 56 53"),
        0x2CC2: bytes.fromhex("55 89 E5 57 56"),
        0x1C32: bytes.fromhex("8B 45 0C 83 F8 CA 7F 1B 83 F8 C8"),
        0x1CA2: bytes.fromhex("8B 45 10 83 F8 CA 7F 1A 83 F8 C8"),
        0x1C5F: bytes.fromhex("9C 60 E8"),
        0x1C75: bytes.fromhex("83 FE 36 72 19 83 FE 38 77 14"),
        0x1CCE: bytes.fromhex("8B 45 08 83 F8 34 74 48 83 F8 35"),
    }
    for rva, expected in expected_core_bytes.items():
        require(rva_bytes(core, rva, len(expected)) == expected,
                f"compatibility core bytes changed at RVA 0x{rva:X}")

    compact_slot_53 = struct.unpack(
        "<ii", rva_bytes(client, 0x7E23F0 + 52 * 8, 8)
    )
    expanded_slot_53 = struct.unpack(
        "<ii", rva_bytes(client, 0x7E2580 + 52 * 8, 8)
    )
    require((compact_slot_53[0], compact_slot_53[1] + 32) == (0x47, 0x85),
            "compact equipment table no longer yields slot-53 draw coordinates")
    require((expanded_slot_53[0], expanded_slot_53[1] + 32) == (0x89, 0xE8),
            "expanded equipment table no longer yields slot-53 draw coordinates")
    native_skill_1016_target = struct.unpack(
        "<I", rva_bytes(client, 0x569411 + 16 * 4, 4)
    )[0]
    require(native_skill_1016_target == 0x00967B8B,
            "native beginner-skill 1016 dispatch target changed")

    for fragment in (
        "kFrenzyTotemItemId = 1189999",
        "LOAD: BeiDouSetItemCompat v22 frenzy-totem-1013-dispatch",
        "kFrenzyTotemBodyPart = 53",
        "LoadLibraryA(kCoreDllName)",
        "kBodyPartLookupHookSite = 0x004606A0",
        "kAccessoryDataPathHookSite = 0x005C9734",
        "kDrawItemIconHookSite = 0x005D6458",
        "kEquipSlotHitTestHookSite = 0x007FEC32",
        "kEquipRequirementHookSite = 0x00460358",
        "kKeyboardDispatchHookSite = 0x0094F89E",
        "kActiveSkillDispatchHookSite = 0x009678F9",
        "kEquipStoreHookSite = 0x0047B088",
        "kEquipLookupHookSite = 0x0042831E",
        "kEquipLoginResetHookSite = 0x004E5CBD",
        "kEquipLoginStoreHookSite = 0x004E5D03",
        "kEquipDrawLoopHookSite = 0x007FEE79",
        "kCoreKeyboardDispatchOffset = 0x1425",
        "kCoreActiveSkillDispatchOffset = 0x149A",
        "kCoreEquipStoreOffset = 0x1C32",
        "kCoreEquipLookupOffset = 0x1CA2",
        "kCoreEquipLoginResetOffset = 0x1C5F",
        "kCoreEquipLoginStoreOffset = 0x1C75",
        "kCoreEquipDrawLoopOffset = 0x1CCE",
        "WaitForCoreHooks(coreBase)",
        "InstallChainedHook",
        "HookTotemBodyPartLookup",
        "HookTotemAccessoryDataPath",
        "HookTotemDrawItemIcon",
        "HookTotemEquipSlotHitTest",
        "HookTotemEquipRequirement",
        "HookTotemKeyboardDispatch",
        "HookTotemActiveSkillDispatch",
        "HookTotemEquipStore",
        "HookTotemEquipLookup",
        "HookTotemEquipLoginReset",
        "HookTotemEquipLoginStore",
        "HookTotemEquipDrawLoop",
        "TotemReplaceEquippedItem",
        "TotemCopyEquippedItem",
        "TotemResetEquippedItem",
        "void* zref[2]",
        "zref[1] = item",
        "pushl $0",
        "kReleaseClientItemAddress = 0x00428A50",
        "x >= 138 && x <= 168 && y >= 198 && y <= 228",
        "int __cdecl HookTotemBodyPartLookup(int itemId, int gender, int* bodyPart, int unknown)",
        "gRealBodyPartLookup(itemId, gender, bodyPart, unknown)",
        '"cmp dword ptr [esp+0x0C], 0x47\\n"',
        '"cmp dword ptr [esp+0x10], 0x85\\n"',
        '"cmp dword ptr [esp+0x0C], 0x89\\n"',
        '"cmp dword ptr [esp+0x10], 0xE8\\n"',
        '"mov dword ptr [esp+0x0C], 0x89\\n"',
        '"mov dword ptr [esp+0x10], 0xE5\\n"',
        '"cmp ecx, 1016\\n"',
        '"push 0x0094FA20\\n"',
        '"cmp esi, 1016\\n"',
        '"push 0x009691AC\\n"',
        '"cmp eax, -53\\n"',
        '"cmp esi, 53\\n"',
        '"cmp eax, 53\\n"',
        '"push 0x0047B152\\n"',
        '"push 0x004283F3\\n"',
        '"push 0x004E5D0A\\n"',
        '"push 0x007FEEEC\\n"',
        "core keeps 54/55/56",
    ):
        require(fragment in source, f"missing client slot contract: {fragment}")

    require("3019999" not in source,
            "invalid setup-item ID remains in the client equipment hook")

    for forbidden in (
        "InstallDirectHook(accessoryDataPath",
        "InstallDirectHook(drawItemIcon",
        "InstallHook(\n            bodyPartLookup",
        "InstallHook(\n            equipSlotHitTest",
        "InstallHook(\n            equipRequirement",
    ):
        require(forbidden not in source,
                f"slot DLL must not patch compatibility-core code: {forbidden}")

    require('kSetItemDllName[] = "BeiDouSetItemCompat.dll"' in wrapper,
            "primary compatibility wrapper does not load the slot DLL")
    require("LoadSiblingDll(kSetItemDllName)" in wrapper,
            "slot DLL load call is missing")
    require("TOTEM(53)" in body_part, "server body part is not slot 53")
    require('TOTEM("Po", -53)' in equip_slot, "server equip slot is not -53")

    print("Frenzy Totem client slot contract ok: item=1189999 slot=53")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

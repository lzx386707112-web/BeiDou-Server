#!/usr/bin/env python3
"""Offline contract checks for the v83 shoulder equipment slot."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch_shoulder_slot_ui import (  # noqa: E402
    CLIENT_UI,
    SLOT_SPECS,
    TARGET_RECORD,
    load_image,
    locate_child_records,
    locate_root_records,
    slots_are_present,
)
from wzpy.canvas import decode_canvas  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def git_blob(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def check_ui_binary_scope() -> None:
    baseline = git_blob(CLIENT_UI)
    current = CLIENT_UI.read_bytes()
    old_image = load_image(baseline)
    new_image = load_image(current)
    old_root_names, old_root_spans = locate_root_records(old_image, baseline)
    new_root_names, new_root_spans = locate_root_records(new_image, current)
    require(old_root_names == new_root_names, "UIWindow root order changed")
    changed_roots = {
        name
        for name, old_span, new_span in zip(old_root_names, old_root_spans, new_root_spans)
        if baseline[slice(*old_span)] != current[slice(*new_span)]
    }
    require(changed_roots in (set(), {"Equip"}),
            f"unexpected UIWindow root changes: {changed_roots}")

    _, _, old_names, old_spans = locate_child_records(old_image, baseline)
    _, _, new_names, new_spans = locate_child_records(new_image, current)
    require(old_names == new_names, "Equip child order changed")
    changed_children = {
        name
        for name, old_span, new_span in zip(old_names, old_spans, new_spans)
        if baseline[slice(*old_span)] != current[slice(*new_span)]
    }
    require(changed_children in (set(), {TARGET_RECORD}),
            f"unexpected Equip child changes: {changed_children}")


def check_ui_semantics() -> None:
    image = load_image(CLIENT_UI.read_bytes())
    canvas = image.root.get("Equip/backgrnd")
    require((canvas.format, canvas.format2) == (1, 0), "shoulder UI is not ARGB4444")
    pixels = decode_canvas(canvas, region="GMS").convert("RGBA")
    require(pixels.size == (175, 304), f"unexpected Equip background size: {pixels.size}")
    require(slots_are_present(pixels), "extended equipment slots are missing")
    require(len(SLOT_SPECS) == 5, "unexpected extended slot count")


def check_source_contract() -> None:
    body_part = (ROOT / "gms-server/src/main/java/org/gms/client/inventory/BodyPart.java").read_text()
    slots = (ROOT / "gms-server/src/main/java/org/gms/constants/inventory/EquipSlot.java").read_text()
    dll = (ROOT / "tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp").read_text()
    require("SHOULDER(20)" in body_part, "server shoulder body part is not 20")
    require('SHOULDER("Sh", -20)' in slots, "server Sh slot is not -20")
    require("SECONDARY_WEAPON(51)" in body_part, "server secondary-weapon body part is not 51")
    require('SECONDARY_WEAPON("Sw", -51)' in slots,
            "server secondary-weapon slot is not -51")
    require('ROBOT_HEART("Ht", -54)' in slots, "server robot-heart slot is not -54")
    require('BADGE("Ba", -55)' in slots, "server badge slot is not -55")
    require('EMBLEM("Em", -56)' in slots, "server emblem slot is not -56")
    require(dll.count("itemId / 10000 == 115") == 2,
            "client classification hooks are not restricted to 115xxxx")
    require(dll.count("itemId / 10000 == 134 || itemId / 10000 == 135") == 2,
            "client secondary-weapon classification does not cover 134/135")
    draw_hook = dll.split("void HookShoulderDrawItemIcon()", 1)[1].split(
        "bool InstallShoulderSlotHooks()", 1)[0]
    secondary_draw = draw_hook.split('"6:\\n"', 1)[1].split('"5:\\n"', 1)[0]
    require('"cmp dword ptr [esp + 0x0C], 0x26\\n"' in secondary_draw,
            "client secondary-weapon icon does not match native slot-51 x coordinate")
    require('"cmp dword ptr [esp + 0x10], 0x43\\n"' in secondary_draw,
            "client secondary-weapon icon does not match native slot-51 y coordinate")
    require('"mov dword ptr [esp + 0x0C], 0x68\\n"' in secondary_draw and
            '"mov dword ptr [esp + 0x10], 0xE5\\n"' in secondary_draw,
            "client secondary-weapon icon is not moved into the new UI slot")
    require('"call _LogSecondaryWeaponDraw\\n"' in secondary_draw,
            "client secondary-weapon UI draw is not observable in diagnostics")
    require('"cmp eax, 1670000\\n"' in draw_hook and
            '"cmp dword ptr [esp + 0x0C], 0x89\\n"' in draw_hook and
            '"cmp dword ptr [esp + 0x0C], 0xAA\\n"' in draw_hook and
            '"cmp dword ptr [esp + 0x10], 0x85\\n"' in draw_hook and
            '"cmp dword ptr [esp + 0x10], 0x109\\n"' in draw_hook and
            '"mov dword ptr [esp + 0x0C], 0x47\\n"' in draw_hook,
            "client robot-heart icon does not map both slot-54 layouts to the heart UI position")
    require('"cmp eax, 1180000\\n"' in draw_hook and
            '"cmp dword ptr [esp + 0x10], 0xA6\\n"' in draw_hook and
            '"cmp dword ptr [esp + 0x10], 0xE8\\n"' in draw_hook and
            '"mov dword ptr [esp + 0x0C], 0x68\\n"' in draw_hook,
            "client badge icon does not map both slot-55 layouts to the badge UI position")
    require('"cmp eax, 1190000\\n"' in draw_hook and
            '"cmp dword ptr [esp + 0x10], 0xC7\\n"' in draw_hook and
            '"cmp dword ptr [esp + 0x0C], 0x190\\n"' in draw_hook and
            '"cmp dword ptr [esp + 0x10], 0x14C\\n"' in draw_hook and
            '"mov dword ptr [esp + 0x0C], 0x89\\n"' in draw_hook,
            "client emblem icon does not map both slot-56 layouts to the emblem UI position")
    require("kShoulderEquipDataPathImmediateAddress" in dll,
            "client equipment data path patch is missing")
    require("kExtendedAccessoryEquipDataPathAddress = 0x005C9734" in dll,
            "client extended-accessory data path hook is missing")
    secondary_contract = dll.split("bool IsExplorerJobBranch(", 1)[1].split(
        "int __fastcall HookEquipRequirementCheck(", 1
    )[0]
    explorer_branches = {
        135220: 110,
        135221: 120,
        135222: 130,
        135223: 210,
        135224: 220,
        135225: 230,
        135226: 310,
        135227: 320,
        135228: 420,
        135290: 510,
        135291: 520,
    }
    for category, first_job in explorer_branches.items():
        require(
            f"if (category == {category}) return IsExplorerJobBranch(job, {first_job});" in
            secondary_contract,
            f"client secondary category {category} does not map to job branch {first_job}")
    require("if (category == 135229) return false;" in secondary_contract,
            "client must disable the unsupported Night Lord secondary category")
    for first_job in (1100, 1200, 1300, 1400, 1500):
        require(f"IsCygnusJobBranch(job, {first_job})" in secondary_contract,
                f"client Cygnus secondary does not include job branch {first_job}")
    require('optimize("no-jump-tables")' in secondary_contract,
            "client secondary classifier may emit an incompatible jump table")
    require(secondary_contract.rstrip().endswith("return false;\n}"),
            "client does not reject unknown secondary categories")
    requirement_hook = dll.split("int __fastcall HookEquipRequirementCheck(", 1)[1].split(
        "bool BytesEqual(", 1
    )[0]
    require("itemPrefix == 118 || itemPrefix == 119 || itemPrefix == 167" in
            requirement_hook,
            "client sends unsupported extended accessories to the legacy requirement checker")
    require("if (!extendedAccessory)" in requirement_hook and
            "result = gRealEquipRequirementCheck(" in requirement_hook,
            "client does not bypass the legacy requirement checker for extended accessories")
    require("!CanEquipMigratedSecondaryWeapon(itemId, job) ? 0 : result" in requirement_hook,
            "client does not mark invalid secondary weapons as disabled")
    require('"cmp eax, 118\\n"' in dll and '"cmp eax, 119\\n"' in dll and
            '"cmp eax, 167\\n"' in dll and '"push 0x005C97A9\\n"' in dll,
            "client extended accessories do not use the proven Accessory path")
    require("kShoulderCombatStatFilterImmediateAddress" in dll,
            "client shoulder stat aggregation patch is missing")
    install_hook = dll.split("bool InstallShoulderSlotHooks()", 1)[1].split(
        "InstallEquipRequirementDiagnosticHook", 1
    )[0]
    require("WriteCheckedByte(kSecondaryWeaponFirstStatSlotCheckImmediateAddress" not in
            install_hook,
            "client must preserve the first native exact-slot-51 special case")
    require("WriteCheckedByte(kSecondaryWeaponFinalStatSlotCheckImmediateAddress" not in
            install_hook,
            "client must preserve the final native exact-slot-51 special case")
    require("native exact-slot-51 handling preserved" in install_hook,
            "client does not log the preserved slot-51 behavior")
    require("AddVectoredExceptionHandler(1, &LogEquipFatalException)" in dll and
            '"EQUIP EXCEPTION: code=%08X eip=%08X operation=%u target=%08X "' in dll,
            "client fatal equipment diagnostics are missing")
    require("kEquipWindowInitialSlotLimitAddress" not in dll and
            "kEquipWindowLoopSlotLimitAddress" not in dll and
            "WriteEquipWindowSlotLimits(" not in dll,
            "client must not extend the fixed 51-slot equipment object arrays")
    require('{"shoulder equipment icon position"' not in dll,
            "client isolation build must not install the global item-icon draw hook")
    require('{"shoulder body-part validation"' not in dll and
            '{"shoulder body-part lookup"' not in dll,
            "client isolation build must not install body-part entry hooks")
    install_hooks = dll.split("DWORD WINAPI InstallHooks(LPVOID)", 1)[1].split(
        "}  // namespace", 1
    )[0]
    require("InstallEquipRequirementDiagnosticHook();" not in install_hooks,
            "client isolation build must not install requirement-call hooks")


def main() -> None:
    check_ui_binary_scope()
    check_ui_semantics()
    check_source_contract()
    print("extended equipment slots passed: body parts 20/51/54/55/56, guarded hooks, exact UI record scope")


if __name__ == "__main__":
    main()

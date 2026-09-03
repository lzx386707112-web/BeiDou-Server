#!/usr/bin/env python3
"""Static contracts for the synchronized 50,000 HP/MP client and server protocol."""

from __future__ import annotations

import re
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CLIENT = ROOT / "clien/BeiDou.exe"
DLL_SOURCE = ROOT / "tool/client-debug/dawn-warrior-skill-compat/HpMpExpansionWrapper.cpp"
ABSTRACT_CHARACTER = ROOT / "gms-server/src/main/java/org/gms/client/AbstractCharacterObject.java"
CHARACTER = ROOT / "gms-server/src/main/java/org/gms/client/Character.java"
PACKETS = ROOT / "gms-server/src/main/java/org/gms/util/PacketCreator.java"
MAX_STAT_COMMAND = ROOT / "gms-server/src/main/java/org/gms/client/command/commands/gm2/MaxStatCommand.java"
CHARACTER_SCHEMA = ROOT / "gms-server/src/main/resources/db/migration/V1.0.6__create_characters.sql"
IMAGE_BASE = 0x00400000


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def array_body(source: str, name: str) -> str:
    match = re.search(rf"constexpr\s+[^;=]+\s+{name}\[\]\s*=\s*\{{(.*?)\}};", source, re.S)
    require(match is not None, f"missing client patch table: {name}")
    return match.group(1)


def address_array(source: str, name: str) -> list[int]:
    return [int(value, 16) for value in re.findall(r"0x[0-9A-Fa-f]+", array_body(source, name))]


def movsx_array(source: str) -> list[tuple[int, int]]:
    return [
        (int(address, 16), int(modrm, 16))
        for address, modrm in re.findall(
            r"\{\s*(0x[0-9A-Fa-f]+)\s*,\s*(0x[0-9A-Fa-f]+)\s*\}",
            array_body(source, "kHpMpMovsxSites"),
        )
    ]


def bytes_at(client: bytes, address: int, size: int) -> bytes:
    offset = address - IMAGE_BASE
    require(0 <= offset <= len(client) - size, f"client address outside image: {address:#x}")
    return client[offset:offset + size]


def call_target(client: bytes, address: int) -> int:
    instruction = bytes_at(client, address, 5)
    require(instruction[0] == 0xE8, f"expected CALL at {address:#x}")
    return address + 5 + struct.unpack("<i", instruction[1:])[0]


def check_client_contract() -> None:
    source = DLL_SOURCE.read_text(encoding="utf-8")
    client = CLIENT.read_bytes()

    decode = address_array(source, "kHpMpDecodeSites")
    tear_short = address_array(source, "kHpMpTearShortSites")
    tear_long = address_array(source, "kHpMpTearLongSites")
    movsx = movsx_array(source)
    compare16 = address_array(source, "kHpMpCompare16Sites")
    test16 = address_array(source, "kHpMpTest16Sites")
    limits = address_array(source, "kHpMpLimitSites")

    require(len(decode) == 13, "client must patch all 13 HP/MP Decode2 calls")
    require(len(tear_short) + len(tear_long) == 25, "client must patch all 25 HP/MP Tear calls")
    require(len(movsx) == 57, "client must patch 57 proven HP/MP sign-extension sites")
    require(len(compare16) == 2 and len(test16) == 2 and len(limits) == 4,
            "client comparison, life-check, or cap patch count changed")

    for address in decode:
        require(call_target(client, address) == 0x0042470C, f"Decode2 signature mismatch: {address:#x}")
    for address in tear_short:
        require(call_target(client, address) == 0x004E80EB, f"Tear_short signature mismatch: {address:#x}")
    for address in tear_long:
        require(call_target(client, address) == 0x004165B1, f"Tear_long signature mismatch: {address:#x}")
    for address, modrm in movsx:
        require(bytes_at(client, address, 3) == bytes((0x0F, 0xBF, modrm)),
                f"movsx signature mismatch: {address:#x}")
    for address in compare16:
        require(bytes_at(client, address, 3) == bytes.fromhex("66 3b c6"),
                f"16-bit comparison signature mismatch: {address:#x}")
    for address in test16:
        require(bytes_at(client, address, 3) == bytes.fromhex("66 85 c0"),
                f"16-bit life-check signature mismatch: {address:#x}")
    for address in limits:
        require(struct.unpack("<I", bytes_at(client, address, 4))[0] == 30000,
                f"client cap signature mismatch: {address:#x}")

    require("constexpr int kMaxHpMp = 50000;" in source, "client cap is not 50,000")
    require("ValidateHpMpPatchSites()" in source and "InstallHpMpHooks()" in source,
            "client HP/MP hooks are not fail-closed")
    require("HpMpFakeTear" in source and "HpMpFuseShort" in source and "HpMpFuseLong" in source,
            "client raw storage or Fuse compatibility hook is missing")
    require('constexpr char kCoreDllName[] = "BeiDouSkillCompatCore.dll";' in source,
            "client wrapper does not load the stable compatibility-core filename")
    require("DawnWarriorSkillCompat.v69.dll" not in source,
            "client wrapper still exposes the versioned compatibility filename")


def check_server_contract() -> None:
    abstract = ABSTRACT_CHARACTER.read_text(encoding="utf-8")
    character = CHARACTER.read_text(encoding="utf-8")
    packets = PACKETS.read_text(encoding="utf-8")
    command = MAX_STAT_COMMAND.read_text(encoding="utf-8")
    schema = CHARACTER_SCHEMA.read_text(encoding="utf-8")

    require("public static final int MAX_HP_MP = 50000;" in abstract,
            "server HP/MP cap is not centralized at 50,000")
    require("this.localMaxHp = MAX_HP_MP;" in abstract
            and "this.localMaxMp = MAX_HP_MP;" in abstract
            and "this.clientMaxHp = MAX_HP_MP;" in abstract
            and "this.clientMaxMp = MAX_HP_MP;" in abstract,
            "effective and client HP/MP limits are not fixed at 50,000")
    require("changeStatPool(Integer newHp, Integer newMp, Integer newMaxHp, Integer newMaxMp" in abstract,
            "server HP/MP values are still packed into 16-bit stat slots")
    require("long hpMpPool = calcStatPoolLong(hp, mp, maxhp, maxmp);" not in abstract,
            "server HP/MP path still truncates through calcStatPoolLong")
    require("maxHp >= MAX_HP_MP" in abstract and "maxMp >= MAX_HP_MP" in abstract,
            "AP assignment does not enforce the 50,000 cap")
    require("updateHpMp(localMaxHp, localMaxMp);" in abstract,
            "full heal does not reach the expanded local maximum")

    require("clientMaxHp = MAX_HP_MP;" in character
            and "clientMaxMp = MAX_HP_MP;" in character,
            "client HP/MP limits are not fixed at 50,000 after stat recalculation")
    require("localMaxHp = MAX_HP_MP;" in character
            and "localMaxMp = MAX_HP_MP;" in character,
            "effective HP/MP limits are not fixed at 50,000 after stat recalculation")
    require("Math.min(30000, maxpoint + diffpoint)" not in character,
            "HP/MP ratio updates still use the old 30,000 cap")
    require(character.count("double temp = (double) curpoint * nextMax;") == 2,
            "HP/MP ratio updates can overflow before reaching the 50,000 cap")
    require("Character.MAX_HP_MP" in command, "max-stat command still uses the old cap")

    full_stats = packets[packets.index("private static void addCharStats"):]
    full_stats = full_stats[:full_stats.index("protected static void addCharLook")]
    for getter in ("getHp", "getClientMaxHp", "getMp", "getClientMaxMp"):
        require(f"p.writeInt(chr.{getter}())" in full_stats,
                f"full character packet does not encode {getter} as four bytes")
    require("statupdate.getLeft() == Stat.HP" in packets and "p.writeInt(statupdate.getRight())" in packets,
            "stat-change packets do not encode HP/MP as four bytes")
    require(packets.count("p.writeInt(chr.getHp());") >= 2,
            "both map-change packet variants must encode HP as four bytes")
    ranged_attack = packets[packets.index("public static Packet rangedAttack"):]
    ranged_attack = ranged_attack[:ranged_attack.index("public static Packet magicAttack")]
    require("p.writeInt(chr.getMp());" in ranged_attack
            and "p.writeInt(chr.getClientMaxMp());" in ranged_attack,
            "remote ranged-attack packets must encode MP and MaxMP as four bytes")

    for column in ("`hp`", "`mp`", "`maxhp`", "`maxmp`"):
        line = next((candidate for candidate in schema.splitlines() if column in candidate), "")
        require("INT(11)" in line, f"database column is not wide enough: {column}")


def main() -> None:
    check_client_contract()
    check_server_contract()
    print("HP/MP 50000 contract passed: 105 client sites and synchronized 4-byte server packets")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Contract: Terminus drops on 9400409 and Kemelz drops on 9420522."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SQL_PATH = (
    ROOT
    / "gms-server/src/main/resources/db/migration/"
    "V2.1.78__add_terminus_kemelz_boss_drops.sql"
)
MOB_DIR = ROOT / "gms-server/wz/Mob.wz"
WEAPON_DIR = ROOT / "gms-server/wz/Character.wz/Weapon"
CLIENT_WEAPON_DIR = ROOT / "clien/Data/Character/Weapon"

TERMINUS = (
    1302290, 1312166, 1322216, 1332239, 1372189, 1382223, 1402211, 1412148,
    1422153, 1432179, 1442235, 1452217, 1462205, 1472227, 1482180, 1492191,
)
KEMELZ = (
    1302299, 1312174, 1322224, 1332249, 1372196, 1382232, 1402222, 1412153,
    1422159, 1432189, 1442243, 1452227, 1462214, 1472236, 1482190, 1492200,
)
CHANCE = 700
EXPECTED = (
    {(9400409, item, CHANCE) for item in TERMINUS}
    | {(9420522, item, CHANCE) for item in KEMELZ}
)


def parse_rows(sql: str) -> list[tuple[int, int, int, int, int, int]]:
    return [
        tuple(map(int, match))
        for match in re.findall(
            r"\((\d+), (\d+), (\d+), (\d+), (\d+), (\d+)\)",
            sql,
        )
    ]


def mob_xml(mob_id: int) -> Path:
    padded = MOB_DIR / f"{mob_id:07d}.img.xml"
    if padded.exists():
        return padded
    return MOB_DIR / f"{mob_id}.img.xml"


def main() -> int:
    errors: list[str] = []
    sql = SQL_PATH.read_text(encoding="utf-8")
    if "ON DUPLICATE KEY UPDATE" not in sql:
        errors.append("migration is not idempotent")

    rows = parse_rows(sql)
    parsed = {(dropper, item, chance) for dropper, item, _mn, _mx, _quest, chance in rows}
    bad_qty = [r for r in rows if r[2:5] != (1, 1, 0)]
    if bad_qty:
        errors.append(f"unexpected qty/quest rows: {bad_qty[:5]}")
    if parsed != EXPECTED:
        missing = EXPECTED - parsed
        extra = parsed - EXPECTED
        if missing:
            errors.append(f"missing drop rows: {sorted(missing)[:10]}")
        if extra:
            errors.append(f"extra drop rows: {sorted(extra)[:10]}")
    if len(rows) != len(EXPECTED):
        errors.append(f"row count {len(rows)} != {len(EXPECTED)}")
    if len({(r[0], r[1]) for r in rows}) != len(rows):
        errors.append("duplicate dropper/item pairs")

    for dropper in (9400409, 9420522):
        if not mob_xml(dropper).exists():
            errors.append(f"missing Mob.wz for {dropper}")
    for item in (*TERMINUS, *KEMELZ):
        if not (WEAPON_DIR / f"{item:08d}.img.xml").exists():
            errors.append(f"missing server weapon XML for {item}")
        if not (CLIENT_WEAPON_DIR / f"{item:08d}.img").exists():
            errors.append(f"missing client weapon IMG for {item}")

    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"ok: {len(EXPECTED)} terminus/kemelz drop rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

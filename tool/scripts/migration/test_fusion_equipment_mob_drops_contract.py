#!/usr/bin/env python3
"""Contract: fusion-chain weapons on the listed mob drop tables."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SQL_PATH = (
    ROOT
    / "gms-server/src/main/resources/db/migration/"
    "V2.1.77__add_fusion_equipment_mob_drops.sql"
)
MOB_DIR = ROOT / "gms-server/wz/Mob.wz"
WEAPON_DIR = ROOT / "gms-server/wz/Character.wz/Weapon"
CLIENT_WEAPON_DIR = ROOT / "clien/Data/Character/Weapon"

# (dropperid, itemid, chance) after mapping missing 2220102 -> 2230102.
EXPECTED = {
    (8140002, 1332077, 700),
    (8140100, 1382109, 700),
    (8140101, 1402048, 700),
    (7130010, 1462052, 700),
    (7130020, 1472072, 700),
    (7140000, 1332080, 700),
    (8120103, 1402051, 700),
    (8140110, 1462055, 700),
    (8120102, 1472075, 700),
    (8140500, 1332078, 700),
    (8140700, 1382110, 700),
    (7130300, 1402049, 700),
    (9420539, 1462053, 700),
    (9420538, 1472073, 700),
    (8190002, 1492047, 700),
    (2100108, 1312017, 700),
    (2230101, 1372221, 700),
    (2230108, 1402255, 700),
    (2230110, 1412056, 700),
    (2110300, 1492242, 700),
    (210100, 1372005, 700),
    (2230111, 1322006, 700),
    (2300100, 1332067, 700),
    (3000006, 1332070, 700),
    (100134, 1382054, 700),
    (2230103, 1402014, 700),
    (2230104, 1422139, 700),
    (2130103, 1482185, 700),
    (2130103, 1492065, 700),
    (2220100, 1312002, 700),
    (2230102, 1382003, 700),
    (2110200, 1472001, 700),
    (2100104, 1462023, 700),
    (2110301, 1332112, 700),
    (2230105, 1422003, 700),
    (2230106, 1432009, 700),
    (2230109, 1452038, 700),
    (2130100, 1482015, 700),
    (2230200, 1492015, 700),
    (3230300, 1302028, 700),
    (3000005, 1422004, 700),
    (3110301, 1472007, 700),
    (9500325, 1302058, 700),
    (4230106, 1312013, 700),
    (4230105, 1322124, 700),
    (4230107, 1332133, 700),
    (4220000, 1402041, 700),
    (9400011, 1402044, 700),
    (9400100, 1422011, 700),
    (9500317, 1432046, 10000),
    (9400000, 1452114, 7000),
    (3110302, 1482064, 7000),
    (3210100, 1492145, 7000),
    (4230116, 1312018, 7000),
    (3210208, 1332034, 7000),
    (3210205, 1412013, 7000),
    (3210206, 1422015, 7000),
    (3230308, 1432020, 7000),
    (3230405, 1452142, 7000),
    (4230113, 1462181, 7000),
    (4230200, 1472040, 7000),
    (4230201, 1482016, 7000),
    (9001012, 1492016, 7000),
    (5300001, 1492088, 7000),
    (4230600, 1322159, 7000),
    (4230300, 1382055, 7000),
    (4230400, 1402149, 7000),
    (4230123, 1412083, 7000),
    (4230125, 1452143, 7000),
    (4230126, 1462132, 7000),
    (4230502, 1402029, 7000),
    (4230501, 1322125, 7000),
    (4230120, 1322209, 7000),
    (4230115, 1482060, 7000),
    (4230109, 1492146, 7000),
    (4230110, 1312014, 7000),
    (5140000, 1432017, 7000),
    (5130108, 1472054, 7000),
    (5150000, 1452115, 7000),
    (5130107, 1462103, 7000),
    (5120505, 1482088, 7000),
    (6230601, 1302094, 7000),
    (6230602, 1322126, 7000),
    (6300005, 1372079, 7000),
    (7130010, 1472049, 7000),
    (7130002, 1492206, 7000),
    (7130004, 1372138, 7000),
    (7130101, 1302214, 7000),
    (7130001, 1332185, 7000),
    (7130103, 1382201, 7000),
    (8110300, 1452169, 7000),
    (8140001, 1462158, 7000),
    (8140002, 1382013, 7000),
    (8140000, 1402038, 7000),
    (8130100, 1402050, 7000),
    (8140100, 1402063, 7000),
    (8140701, 1412040, 7000),
    (8170000, 1382060, 7000),
    (8160000, 1432056, 7000),
    (8180000, 1382037, 7000),
    (8180001, 1402169, 7000),
    (8150200, 1302226, 7000),
    (8150201, 1322134, 7000),
    (8200004, 1432066, 7000),
    (8142000, 1312097, 7000),
    (8143000, 1322137, 7000),
    (8142100, 1402114, 7000),
    (8141100, 1452132, 7000),
    (8150000, 1462121, 7000),
    (8200005, 1482105, 7000),
    (8200004, 1492104, 7000),
    (8200006, 1302336, 7000),
    (8220003, 1372205, 7000),
    (8220004, 1382243, 7000),
    (8220005, 1492148, 7000),
}


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
    if "mapped to 2230102" not in sql:
        errors.append("missing remap note for 1382003")

    rows = parse_rows(sql)
    if any(dropper == 2220102 for dropper, *_ in rows):
        errors.append("migration still references missing mob 2220102")
    parsed = {(dropper, item, chance) for dropper, item, mn, mx, quest, chance in rows}
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

    for dropper, item, _chance in sorted(EXPECTED):
        if not mob_xml(dropper).exists():
            errors.append(f"missing Mob.wz for {dropper}")
        weapon = WEAPON_DIR / f"{item:08d}.img.xml"
        if not weapon.exists():
            errors.append(f"missing server weapon XML for {item}")
        client = CLIENT_WEAPON_DIR / f"{item:08d}.img"
        if not client.exists():
            errors.append(f"missing client weapon IMG for {item}")

    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"ok: {len(EXPECTED)} fusion equipment drop rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

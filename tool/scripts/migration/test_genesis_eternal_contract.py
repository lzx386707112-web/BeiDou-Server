import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tool/scripts/migration/migrate_genesis_eternal_weapons.py"


def load_migration_module():
    spec = importlib.util.spec_from_file_location("genesis_eternal", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tms_genesis_weapons_cover_all_legacy_weapon_categories():
    migration = load_migration_module()
    assert migration.source_contract() == (
        1302355, 1312213, 1322264, 1402268, 1412189, 1422197, 1432227, 1442285,
        1372237, 1382274,
        1452266, 1462252,
        1332289, 1472275,
        1482232, 1492245,
    )
    assert {spec.item_id // 10000 for spec in migration.ITEM_SPECS} == set(range(130, 150)) - {134, 135, 136, 139}
    assert all(
        tuple(name for name, _ in values) == ("name", "desc")
        and dict(values)["desc"] == migration.ITEM_DESCRIPTION
        for values in migration.source_strings().values()
    )


def test_destiny_and_eternal_equipment_strings_have_descriptions():
    migration = load_migration_module().equipment
    strings = migration.source_strings()
    for spec, values in strings.items():
        expected = (
            migration.DESTINY_WEAPON_DESCRIPTION
            if spec.weapon
            else migration.ETERNAL_ARMOR_DESCRIPTION
        )
        assert tuple(name for name, _ in values) == ("name", "desc")
        assert dict(values)["desc"] == expected


def test_genesis_weapons_are_bound_to_eternal_sets_and_karing_drops():
    set_manager = (
        ROOT / "gms-server/src/main/java/org/gms/server/SetItemManager.java"
    ).read_text(encoding="utf-8")
    sql = (
        ROOT / "gms-server/src/main/resources/db/migration/"
        "V2.1.58__add_karing_compatible_drops.sql"
    ).read_text(encoding="utf-8")
    assert '"天命/创世/永恒"' in set_manager
    assert "mergeWeapons(finalWeapons, genesisWeapons[job])" in set_manager
    for item_id in load_migration_module().source_contract():
        assert str(item_id) in set_manager
        assert f"(8880842, {item_id}, 1, 1, 0, 10000)" in sql

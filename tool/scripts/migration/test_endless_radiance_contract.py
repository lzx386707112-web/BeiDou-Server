import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tool/scripts/migration/migrate_endless_radiance_equipment.py"


def load_migration_module():
    spec = importlib.util.spec_from_file_location("endless_radiance", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tms_endless_radiance_items_and_outputs_are_complete():
    migration = load_migration_module()
    assert migration.source_set_contract() == (
        1113341,
        1122447,
        1143471,
        1113360,
        1012911,
    )
    assert all(spec.target_level == 220 for spec in migration.ITEM_SPECS)
    names = migration.source_strings()
    assert all(
        tuple(name for name, _ in values) == ("name", "desc")
        and dict(values)["desc"] == migration.ITEM_DESCRIPTION
        for values in names.values()
    )
    migration.verify(names)

    for spec in migration.ITEM_SPECS:
        root = ET.parse(spec.server_path).getroot()
        info = next(child for child in root if child.get("name") == "info")
        req_level = next(child for child in info if child.get("name") == "reqLevel")
        assert req_level.get("value") == "220"
        assert all(child.get("name") != "setItemID" for child in info)


def test_server_catalog_and_karing_drop_include_endless_radiance():
    set_manager = (
        ROOT / "gms-server/src/main/java/org/gms/server/SetItemManager.java"
    ).read_text(encoding="utf-8")
    character = (
        ROOT / "gms-server/src/main/java/org/gms/client/Character.java"
    ).read_text(encoding="utf-8")
    sql = (
        ROOT
        / "gms-server/src/main/resources/db/migration/"
        "V2.1.58__add_karing_compatible_drops.sql"
    ).read_text(encoding="utf-8")

    assert 'new Definition(id, -1, "无尽辉耀"' in set_manager
    assert "definition.jobIndex() < 0" in set_manager
    for stat in ("STR", "DEX", "INT", "LUK"):
        assert f'setItemBonus.get("{stat}")' in character
    for item_id in (1113341, 1122447, 1143471, 1113360, 1012911):
        assert f"(8880842, {item_id}, 1, 1, 0, 10000)" in sql

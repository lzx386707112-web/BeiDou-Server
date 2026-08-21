import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
RESOURCE = ROOT / "gms-server/src/main/resources/equipment-catalog"
sys.path.insert(0, str(ROOT / "tool/scripts/migration"))

import migrate_destiny_eternal_equipment as destiny  # noqa: E402
import migrate_endless_radiance_equipment as radiance  # noqa: E402
import migrate_genesis_eternal_weapons as genesis  # noqa: E402


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_exporter_is_read_only_and_uses_content_addressed_icon_cache():
    exporter = read("tool/scripts/preview/export_equipment_catalog.py")
    assert "decode_canvas" in exporter
    assert "hashlib.sha256(data)" in exporter
    assert "encode_image_body" not in exporter
    assert ".save_as(" not in exporter
    assert "CLIENT_CHARACTER" in exporter
    assert "SERVER_CHARACTER" in exporter


def test_generated_catalog_and_atlases_are_consistent():
    catalog = json.loads((RESOURCE / "catalog.json").read_text(encoding="utf-8"))
    assert catalog["version"] == 1
    assert catalog["cellSize"] == 48
    assert len(catalog["items"]) >= 10_000
    ids = [item["id"] for item in catalog["items"]]
    assert len(ids) == len(set(ids))
    assert 1_000_000 <= min(ids) < max(ids) < 2_000_000

    icon_items = 0
    for category, atlas_info in catalog["atlases"].items():
        path = RESOURCE / "atlases" / f"{category}.png"
        assert path.is_file()
        category_items = [item for item in catalog["items"]
                          if item["category"] == category]
        assert len(category_items) == atlas_info["count"]
        with Image.open(path) as source_atlas:
            atlas = source_atlas.convert("RGBA")
            assert atlas.size == (atlas_info["width"], atlas_info["height"])
            for item in category_items:
                if not item["icon"]:
                    continue
                cell = atlas.crop((item["x"], item["y"],
                                   item["x"] + catalog["cellSize"],
                                   item["y"] + catalog["cellSize"]))
                assert cell.getbbox() is not None, item["id"]
                icon_items += 1
    assert icon_items >= 10_000


def test_migrated_set_equipment_names_and_descriptions_are_complete():
    catalog = json.loads((RESOURCE / "catalog.json").read_text(encoding="utf-8"))
    items = {item["id"]: item for item in catalog["items"]}
    expected = {}
    for source in (
        destiny.source_strings(),
        radiance.source_strings(),
        genesis.source_strings(),
    ):
        expected.update({spec.item_id: dict(values) for spec, values in source.items()})

    assert len(expected) == 72
    for item_id, strings in expected.items():
        assert items[item_id]["name"] == strings["name"]
        assert items[item_id]["desc"] == strings["desc"]


def test_backend_and_frontend_catalog_contract_is_connected():
    service = read(
        "gms-server/src/main/java/org/gms/service/EquipmentCatalogService.java"
    )
    controller = read(
        "gms-server/src/main/java/org/gms/controller/SetItemController.java"
    )
    asset_controller = read(
        "gms-server/src/main/java/org/gms/controller/EquipmentAssetController.java"
    )
    api = read("gms-ui/src/api/equipmentCatalog.ts")
    view = read("gms-ui/src/views/game/equipmentCatalog/index.vue")
    tooltip = read(
        "gms-ui/src/views/game/equipmentCatalog/EquipmentTooltip.vue"
    )
    route = read("gms-ui/src/router/routes/modules/game.ts")

    assert 'CATALOG_RESOURCE = "/equipment-catalog/catalog.json"' in service
    assert "public EquipmentCatalogPageDTO catalog(" in service
    assert "public byte[] icon(" in service
    assert '"/equipment/catalog"' in controller
    assert '"/assets/equipment-icons"' in asset_controller
    assert "/setItem/v1/equipment/catalog" in api
    assert "EquipmentTooltip" in view
    assert "@mouseenter" not in view
    assert "stats" in tooltip
    assert "equipmentCatalog/index.vue" in route

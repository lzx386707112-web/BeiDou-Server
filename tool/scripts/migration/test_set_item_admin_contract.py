from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_runtime_uses_validated_dynamic_overrides_with_default_fallback():
    manager = read("gms-server/src/main/java/org/gms/server/SetItemManager.java")
    overrides = read(
        "gms-server/src/main/java/org/gms/server/SetItemBonusOverrides.java"
    )
    service = read(
        "gms-server/src/main/java/org/gms/service/SetItemConfigService.java"
    )
    character = read("gms-server/src/main/java/org/gms/client/Character.java")

    assert "SetItemBonusOverrides.snapshot()" in manager
    assert "return DEFINITIONS;" in manager
    assert "for (Map.Entry<String, Integer> entry : replacement.entrySet())" in manager
    assert "effective.remove(entry.getKey())" in manager
    assert "Collections.unmodifiableMap" in overrides
    assert "!request.getTiers().keySet().equals(requiredCounts)" in service
    assert "SetItemBonusOverrides.REMOVED_VALUE" in service
    assert "removeDefinitionOverrides(updated, definitionId)" in service
    assert "SetItemBonusOverrides.replaceAll" in service
    assert "character.refreshSetItemBonuses()" in service
    assert 'stat.toLowerCase(Locale.ROOT)' in service
    assert "public void refreshSetItemBonuses()" in character


def test_admin_api_and_database_config_support_read_update_and_reset():
    controller = read(
        "gms-server/src/main/java/org/gms/controller/SetItemController.java"
    )
    migration = read(
        "gms-server/src/main/resources/db/migration/"
        "V2.1.59__add_set_item_bonus_overrides.sql"
    )

    assert '@GetMapping("/" + ApiConstant.LATEST + "/catalog")' in controller
    assert '@PutMapping("/" + ApiConstant.LATEST + "/{definitionId}")' in controller
    assert '@DeleteMapping("/" + ApiConstant.LATEST + "/{definitionId}")' in controller
    assert migration.count("set_item_bonus_overrides") >= 6
    assert "WHERE NOT EXISTS" in migration
    assert migration.count("`lang_extend`") == 2

    config_service = read(
        "gms-server/src/main/java/org/gms/service/ConfigService.java"
    )
    update_method = config_service.split("public void updateConfig", 1)[1].split(
        "public void deleteConfig", 1
    )[0]
    assert "refreshSpecialConfig(gameConfigDO.getConfigCode())" in update_method
    assert ".reloadAndRefresh()" in config_service


def test_admin_ui_exposes_every_server_supported_stat():
    manager = read("gms-server/src/main/java/org/gms/server/SetItemManager.java")
    api = read("gms-ui/src/api/setItem.ts")
    view = read("gms-ui/src/views/game/setItem/index.vue")
    route = read("gms-ui/src/router/routes/modules/game.ts")
    zh = read("gms-ui/src/views/game/setItem/locale/zh-CN.ts")
    en = read("gms-ui/src/views/game/setItem/locale/en-US.ts")

    stat_block = re.search(r"STAT_KEYS = \{(.*?)\};", manager, re.DOTALL)
    assert stat_block is not None
    stat_keys = re.findall(r'"([A-Za-z]+)"', stat_block.group(1))
    assert stat_keys
    for stat in stat_keys:
        assert f"'setItem.stat.{stat}'" in zh
        assert f"'setItem.stat.{stat}'" in en

    assert "/setItem/v1/catalog" in api
    assert "updateSetItem" in view
    assert "resetSetItem" in view
    assert "Object.keys(editValues[tier.requiredCount]" in view
    assert "removeEditorStat" in view
    assert "SET_ITEM_STAT_KEYS.filter" in view
    assert "stat.toLowerCase()" in view
    assert "roles: ['admin']" in route
    assert "@/views/game/setItem/index.vue" in route


def test_dynamic_catalog_supports_create_disable_restore_and_custom_delete():
    manager = read("gms-server/src/main/java/org/gms/server/SetItemManager.java")
    state = read(
        "gms-server/src/main/java/org/gms/server/SetItemBonusOverrides.java"
    )
    service = read(
        "gms-server/src/main/java/org/gms/service/SetItemConfigService.java"
    )
    controller = read(
        "gms-server/src/main/java/org/gms/controller/SetItemController.java"
    )
    migration = read(
        "gms-server/src/main/resources/db/migration/"
        "V2.1.60__add_dynamic_set_item_catalog.sql"
    )

    assert "FIRST_CUSTOM_DEFINITION_ID = 20_000" in service
    assert "buildDefinition(request, definitionId, true)" in service
    assert "同一件装备不能出现在多个套装槽位中" in service
    assert "SUPPORTED_STAT_KEYS.contains" in service
    assert "ItemConstants.getInventoryType(itemId) != InventoryType.EQUIP" in service
    assert "removeDefinitionOverrides(bonuses, definitionId)" in service
    assert "replaceAll" in state
    assert "disabledBuiltInIds" in state
    assert ".filter(definition -> !disabled.contains(definition.id()))" in manager
    assert '@PostMapping("/" + ApiConstant.LATEST + "/custom")' in controller
    assert '"/{definitionId}/enabled"' in controller
    assert '"/custom/{definitionId}"' in controller
    assert migration.count("set_item_catalog_customizations") >= 6
    assert migration.count("`lang_extend`") == 2


def test_equipment_fuzzy_search_and_preview_are_connected():
    catalog_service = read(
        "gms-server/src/main/java/org/gms/service/EquipmentCatalogService.java"
    )
    api = read("gms-ui/src/api/setItem.ts")
    view = read("gms-ui/src/views/game/setItem/index.vue")
    create_view = read(
        "gms-ui/src/views/game/setItem/SetItemCreateModal.vue"
    )
    icon_util = read("gms-ui/src/utils/mapleStoryAPI.ts")

    assert "String.valueOf(item.id()).contains(query)" in catalog_service
    assert "item.name().toLowerCase(Locale.ROOT).contains(query)" in catalog_service
    assert "/setItem/v1/equipment/search" in api
    assert "getEquipmentCatalog" in create_view
    assert "getEquipmentPreviewUrl(item.id)" in create_view
    assert 'VITE_API_BASE_URL' in icon_util
    assert '/assets/equipment-icons/${id}.png' in icon_util
    assert "getIconUrl('item', id, 'GMS', '255')" in icon_util
    assert "getIconUrl('item', id, 'GMS', '83')" in icon_util
    assert "previewEquipment(record)" in view

INSERT INTO `game_config`(`config_type`, `config_sub_type`, `config_clazz`, `config_code`, `config_value`, `config_desc`, `update_time`)
SELECT cfg.config_type, cfg.config_sub_type, cfg.config_clazz, cfg.config_code, cfg.config_value, cfg.config_desc, NOW()
FROM (
    SELECT 'server' config_type, 'SoloMapling' config_sub_type, 'java.lang.Boolean' config_clazz, 'solo_mapling_feature_fm_bots_enabled' config_code, 'true' config_value, 'solo_mapling_feature_fm_bots_enabled' config_desc
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_fm_merchants_enabled', 'true', 'solo_mapling_feature_fm_merchants_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_fm_region_fill_enabled', 'true', 'solo_mapling_feature_fm_region_fill_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_henesys_crowd_enabled', 'true', 'solo_mapling_feature_henesys_crowd_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_henesys_market_crowd_enabled', 'true', 'solo_mapling_feature_henesys_market_crowd_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_henesys_park_crowd_enabled', 'true', 'solo_mapling_feature_henesys_park_crowd_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_henesys_potion_shop_crowd_enabled', 'true', 'solo_mapling_feature_henesys_potion_shop_crowd_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_henesys_game_zone_crowd_enabled', 'true', 'solo_mapling_feature_henesys_game_zone_crowd_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_gacha_bots_enabled', 'true', 'solo_mapling_feature_gacha_bots_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_opq_lobby_bots_enabled', 'true', 'solo_mapling_feature_opq_lobby_bots_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_blackjack_tables_enabled', 'true', 'solo_mapling_feature_blackjack_tables_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_casino_npc_enabled', 'true', 'solo_mapling_feature_casino_npc_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_rps_npc_enabled', 'true', 'solo_mapling_feature_rps_npc_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_conversation_enabled', 'true', 'solo_mapling_feature_conversation_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_hot_potato_enabled', 'true', 'solo_mapling_feature_hot_potato_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_tutorial_bot_enabled', 'true', 'solo_mapling_feature_tutorial_bot_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_pet_park_jq_bots_enabled', 'true', 'solo_mapling_feature_pet_park_jq_bots_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_pet_park_social_bots_enabled', 'true', 'solo_mapling_feature_pet_park_social_bots_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_game_zone_host_bots_enabled', 'true', 'solo_mapling_feature_game_zone_host_bots_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_potion_shop_drop_game_enabled', 'true', 'solo_mapling_feature_potion_shop_drop_game_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_feature_scroll_bots_enabled', 'true', 'solo_mapling_feature_scroll_bots_enabled'
) cfg
WHERE NOT EXISTS (
    SELECT 1 FROM `game_config` g WHERE g.`config_code` = cfg.config_code
);

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT lang.lang_type, 'game_config', lang.lang_code, lang.lang_value, NULL
FROM (
    SELECT 'zh-CN' lang_type, 'solo_mapling_feature_fm_bots_enabled' lang_code, '是否启用 FM 入口假人' lang_value
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_fm_merchants_enabled', '是否启用 FM 商人假人'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_fm_region_fill_enabled', '是否启用自由市场区域商店填充'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_henesys_crowd_enabled', '是否启用射手村主地图人群'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_henesys_market_crowd_enabled', '是否启用射手村市场人群'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_henesys_park_crowd_enabled', '是否启用射手村公园人群'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_henesys_potion_shop_crowd_enabled', '是否启用射手村药店人群'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_henesys_game_zone_crowd_enabled', '是否启用射手村游戏区人群'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_gacha_bots_enabled', '是否启用扭蛋假人'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_opq_lobby_bots_enabled', '是否启用 OPQ lobby 假人'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_blackjack_tables_enabled', '是否启用 21 点桌'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_casino_npc_enabled', '是否启用赌场 NPC'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_rps_npc_enabled', '是否启用猜拳 NPC'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_conversation_enabled', '是否启用假人对话系统'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_hot_potato_enabled', '是否启用 Hot Potato 社交系统'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_tutorial_bot_enabled', '是否启用教程岛假人'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_pet_park_jq_bots_enabled', '是否启用宠物公园跳跳假人'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_pet_park_social_bots_enabled', '是否启用宠物公园社交人群'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_game_zone_host_bots_enabled', '是否启用游戏区主持假人'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_potion_shop_drop_game_enabled', '是否启用药店丢物小游戏'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_feature_scroll_bots_enabled', '是否启用卷轴假人转换'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_fm_bots_enabled', 'Enable FM entrance bots.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_fm_merchants_enabled', 'Enable FM merchant bots.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_fm_region_fill_enabled', 'Enable Free Market region shop population.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_henesys_crowd_enabled', 'Enable Henesys main map crowd bots.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_henesys_market_crowd_enabled', 'Enable Henesys Market crowd bots.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_henesys_park_crowd_enabled', 'Enable Henesys Park crowd bots.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_henesys_potion_shop_crowd_enabled', 'Enable Henesys Potion Shop crowd bots.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_henesys_game_zone_crowd_enabled', 'Enable Henesys Game Zone crowd bots.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_gacha_bots_enabled', 'Enable gacha bots.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_opq_lobby_bots_enabled', 'Enable OPQ lobby bots.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_blackjack_tables_enabled', 'Enable blackjack tables.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_casino_npc_enabled', 'Enable casino NPC.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_rps_npc_enabled', 'Enable rock-paper-scissors NPC.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_conversation_enabled', 'Enable bot conversation system.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_hot_potato_enabled', 'Enable Hot Potato social system.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_tutorial_bot_enabled', 'Enable tutorial bot.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_pet_park_jq_bots_enabled', 'Enable Pet Park jump quest bots.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_pet_park_social_bots_enabled', 'Enable Pet Park social crowd bots.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_game_zone_host_bots_enabled', 'Enable Game Zone host bots.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_potion_shop_drop_game_enabled', 'Enable Potion Shop drop game.'
    UNION ALL SELECT 'en-US', 'solo_mapling_feature_scroll_bots_enabled', 'Enable scroll bot conversion.'
) lang
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources` lr
    WHERE lr.`lang_type` = lang.lang_type
      AND lr.`lang_base` = 'game_config'
      AND lr.`lang_code` = lang.lang_code
);

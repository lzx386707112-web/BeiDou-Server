INSERT INTO `game_config`(`config_type`, `config_sub_type`, `config_clazz`, `config_code`, `config_value`, `config_desc`, `update_time`)
SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_henesys_bots_change_maps', 'false', 'solo_mapling_henesys_bots_change_maps', NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM `game_config` WHERE `config_code` = 'solo_mapling_henesys_bots_change_maps'
);

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT 'zh-CN', 'game_config', 'solo_mapling_henesys_bots_change_maps', '是否允许 SoloMapling 射手村假人在射手村/市场/公园之间自动换图', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources` WHERE `lang_type` = 'zh-CN' AND `lang_code` = 'solo_mapling_henesys_bots_change_maps'
);

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT 'en-US', 'game_config', 'solo_mapling_henesys_bots_change_maps', 'Allow SoloMapling Henesys bots to roam between Henesys, Market, and Park maps.', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources` WHERE `lang_type` = 'en-US' AND `lang_code` = 'solo_mapling_henesys_bots_change_maps'
);

UPDATE `game_config`
SET `config_value` = 'false', `update_time` = NOW()
WHERE `config_code` IN (
    'solo_mapling_auto_environment',
    'solo_mapling_henesys_bots_change_maps'
);

UPDATE `game_config`
SET `config_value` = 'true', `update_time` = NOW()
WHERE `config_code` = 'solo_mapling_auto_map_bots_enabled';

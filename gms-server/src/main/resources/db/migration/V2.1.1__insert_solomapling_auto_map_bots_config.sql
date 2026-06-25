INSERT INTO `game_config`(`config_type`, `config_sub_type`, `config_clazz`, `config_code`, `config_value`, `config_desc`, `update_time`)
SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_auto_map_bots_enabled', 'true', 'solo_mapling_auto_map_bots_enabled', NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM `game_config` WHERE `config_code` = 'solo_mapling_auto_map_bots_enabled'
);

INSERT INTO `game_config`(`config_type`, `config_sub_type`, `config_clazz`, `config_code`, `config_value`, `config_desc`, `update_time`)
SELECT 'server', 'SoloMapling', 'java.lang.Integer', 'solo_mapling_auto_map_bots_min', '2', 'solo_mapling_auto_map_bots_min', NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM `game_config` WHERE `config_code` = 'solo_mapling_auto_map_bots_min'
);

INSERT INTO `game_config`(`config_type`, `config_sub_type`, `config_clazz`, `config_code`, `config_value`, `config_desc`, `update_time`)
SELECT 'server', 'SoloMapling', 'java.lang.Integer', 'solo_mapling_auto_map_bots_max', '4', 'solo_mapling_auto_map_bots_max', NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM `game_config` WHERE `config_code` = 'solo_mapling_auto_map_bots_max'
);

INSERT INTO `game_config`(`config_type`, `config_sub_type`, `config_clazz`, `config_code`, `config_value`, `config_desc`, `update_time`)
SELECT 'server', 'SoloMapling', 'java.lang.Integer', 'solo_mapling_auto_map_bots_radius', '350', 'solo_mapling_auto_map_bots_radius', NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM `game_config` WHERE `config_code` = 'solo_mapling_auto_map_bots_radius'
);

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT 'zh-CN', 'game_config', 'solo_mapling_auto_map_bots_enabled', '玩家进入地图时是否自动生成 SoloMapling 假人', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources` WHERE `lang_type` = 'zh-CN' AND `lang_code` = 'solo_mapling_auto_map_bots_enabled'
);

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT 'zh-CN', 'game_config', 'solo_mapling_auto_map_bots_min', '每张地图自动生成假人的最小数量', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources` WHERE `lang_type` = 'zh-CN' AND `lang_code` = 'solo_mapling_auto_map_bots_min'
);

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT 'zh-CN', 'game_config', 'solo_mapling_auto_map_bots_max', '每张地图自动生成假人的最大数量', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources` WHERE `lang_type` = 'zh-CN' AND `lang_code` = 'solo_mapling_auto_map_bots_max'
);

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT 'zh-CN', 'game_config', 'solo_mapling_auto_map_bots_radius', '自动生成假人时相对玩家的随机横向范围', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources` WHERE `lang_type` = 'zh-CN' AND `lang_code` = 'solo_mapling_auto_map_bots_radius'
);
